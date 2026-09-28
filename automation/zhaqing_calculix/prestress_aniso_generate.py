from pathlib import Path  # Use deterministic filesystem paths for the validated baseline and generated prestress model.
import math  # Compute three-dimensional element directions, lengths, slopes, and force-to-strain conversions.
import re  # Parse validated element blocks and replace only the main-cable and hanger section assignments.
import sys  # Receive the validated PR9 baseline INP and generated output INP from the solver workflow.
if len(sys.argv) != 3:  # Require exactly one mother-model path and one generated-model path for reproducibility.
    raise SystemExit('usage: prestress_aniso_generate.py BASELINE_INP OUTPUT_INP')  # Stop explicitly when the workflow invocation is incomplete.
source = Path(sys.argv[1]).resolve()  # Resolve the immutable validated PR9 LC01 mother model.
out = Path(sys.argv[2]).resolve()  # Resolve the force-found anisotropic-prestrain CalculiX output deck.
out.parent.mkdir(parents=True, exist_ok=True)  # Create the generated-model directory before writing numerical evidence.
text = source.read_text()  # Load the validated mother deck once so every unrelated record remains unchanged.
lines = text.splitlines()  # Split the source only for extracting node coordinates and element connectivity.
nodes = {}  # Store original global node coordinates keyed by validated node identifier.
elements = {}  # Store original element type, semantic set, and connectivity keyed by validated element identifier.
sets = {}  # Store original element identifiers grouped by their semantic element-set names.
i = 0  # Start a single deterministic pass through the validated input deck.
while i < len(lines):  # Parse only node and element records needed for prestress force reconstruction.
    line = lines[i].strip()  # Normalize surrounding whitespace on the current input record.
    upper = line.upper()  # Compare Abaqus/CalculiX keywords without depending on capitalization.
    if upper == '*NODE, NSET=NALL' or upper == '*NODE':  # Enter the validated global node block while excluding output keywords.
        i += 1  # Advance from the node keyword to the first coordinate record.
        while i < len(lines) and not lines[i].lstrip().startswith('*'):  # Read every node until the next keyword begins.
            row = [field.strip() for field in lines[i].split(',')]  # Split the node identifier and its three global coordinates.
            nodes[int(row[0])] = (float(row[1]), float(row[2]), float(row[3]))  # Preserve the exact validated coordinate tuple numerically.
            i += 1  # Move to the next node record or the following keyword.
        continue  # Resume parsing from the keyword reached by the inner node loop.
    if upper.startswith('*ELEMENT,'):  # Enter one validated element block.
        type_match = re.search(r'TYPE=([^,]+)', line, re.I)  # Extract the original finite-element formulation from the keyword.
        set_match = re.search(r'ELSET=([^,]+)', line, re.I)  # Extract the original semantic element set from the keyword.
        element_type = type_match.group(1).strip() if type_match else ''  # Preserve the original formulation string for auditability.
        element_set = set_match.group(1).strip() if set_match else ''  # Preserve the original semantic grouping string for auditability.
        sets.setdefault(element_set, [])  # Initialize this semantic element set before reading connectivity rows.
        i += 1  # Advance from the element keyword to its first connectivity row.
        while i < len(lines) and not lines[i].lstrip().startswith('*'):  # Read every connectivity record until the next keyword begins.
            row = [field.strip() for field in lines[i].split(',') if field.strip()]  # Remove empty comma fields while retaining node order.
            element_id = int(row[0])  # Parse the globally unique validated element identifier.
            elements[element_id] = (element_type, element_set, [int(value) for value in row[1:]])  # Preserve original type, semantic set, and connectivity.
            sets[element_set].append(element_id)  # Register the element under its original semantic set without changing that set.
            i += 1  # Move to the next connectivity record or keyword.
        continue  # Resume parsing from the keyword already reached by the inner element loop.
    i += 1  # Skip every source record unrelated to force-found free-length reconstruction.
def unit_vector(element_id):  # Return the validated three-dimensional unit vector and length of one two-node cable or hanger element.
    node_a, node_b = elements[element_id][2][:2]  # Retrieve the original element end-node identifiers in their validated order.
    point_a, point_b = nodes[node_a], nodes[node_b]  # Recover the corresponding global end-node coordinates.
    delta = tuple(point_b[j] - point_a[j] for j in range(3))  # Form the exact global chord vector from the first node to the second.
    length = math.sqrt(sum(component * component for component in delta))  # Evaluate the validated three-dimensional chord length in millimetres.
    direction = tuple(component / length for component in delta)  # Normalize the chord vector to the element axial unit vector.
    return direction, length  # Return both quantities so force and self-weight calculations use the same validated geometry.
def aniso_line(strain, direction):  # Convert one scalar axial free contraction into CalculiX anisotropic expansion tensor coefficients.
    nx, ny, nz = direction  # Unpack the global axial direction cosines of this original cable or hanger element.
    coefficients = (strain * nx * nx, strain * ny * ny, strain * nz * nz, strain * nx * ny, strain * nx * nz, strain * ny * nz)  # Form strain times n tensor n in CalculiX 11,22,33,12,13,23 component order.
    return ', '.join(f'{value:.12e}' for value in coefficients) + ', 0.\n'  # Write six tensor coefficients plus the zero material-data temperature required by TYPE=ANISO input.
H_KN = 716.1502048515677  # Use the discrete completed-state horizontal main-cable component recovered from the validated PR9 dead-load equilibrium.
A_MAIN = 74.5432224 * 74.5432224  # Preserve the validated equivalent main-cable area in square millimetres.
E_MAIN = 195000.0  # Preserve the validated main-cable elastic modulus in MPa.
A_HANGER = 804.247719  # Preserve the validated hanger T3D2 area in square millimetres.
E_HANGER = 200000.0  # Preserve the validated hanger elastic modulus in MPa.
RHO_HANGER = 7.85e-9  # Preserve the validated hanger density in tonnes per cubic millimetre.
G = 9810.0  # Preserve the validated N-mm-tonne-s gravitational acceleration.
mainspan = []  # Collect one main-span cable chain to recover the actual tower-adjacent segment slope.
for element_id in sets['MAIN_CABLES']:  # Inspect every original B31 main-cable element without modifying connectivity.
    node_a, node_b = elements[element_id][2][:2]  # Retrieve this original main-cable segment's validated end nodes.
    point_a, point_b = nodes[node_a], nodes[node_b]  # Recover the original global end-node coordinates.
    if abs(point_a[1] - 2750.0) < 1.0e-6 and abs(point_b[1] - 2750.0) < 1.0e-6 and min(point_a[0], point_b[0]) >= 0.0 and max(point_a[0], point_b[0]) <= 82000.0:  # Select the positive-y tower-to-tower chain.
        mainspan.append(element_id)  # Preserve this main-span segment for tower-slope recovery.
mainspan.sort(key=lambda element_id: min(nodes[elements[element_id][2][0]][0], nodes[elements[element_id][2][1]][0]))  # Order the selected chain from the left tower to the right tower.
first_a, first_b = elements[mainspan[0]][2][:2]  # Retrieve the first validated segment immediately adjacent to the left tower.
end_dx = nodes[first_b][0] - nodes[first_a][0]  # Compute its longitudinal projection in millimetres.
end_dz = nodes[first_b][2] - nodes[first_a][2]  # Compute its vertical projection in millimetres.
end_slope = abs(end_dz / end_dx)  # Recover the discretized main-span cable slope next to the tower.
T_TOWER_KN = H_KN * math.sqrt(1.0 + end_slope * end_slope)  # Enforce tension continuity between the curved main span and straight side span.
materials = []  # Accumulate unique anisotropic prestress material definitions for main-cable segments and hanger stations.
elsets = []  # Accumulate disjoint section-assignment element sets while preserving the original semantic sets for outputs.
sections = []  # Accumulate replacement B31/T3D2 section cards using unchanged geometric properties.
pretension_nodes = set()  # Collect only nodes belonging to elements that receive imposed free-length contraction.
for sequence, element_id in enumerate(sets['MAIN_CABLES'], start=1):  # Generate one axial-only free-length correction for each validated main-cable segment.
    node_a, node_b = elements[element_id][2][:2]  # Retrieve the validated segment end nodes.
    point_a, point_b = nodes[node_a], nodes[node_b]  # Recover their original global coordinates.
    direction, element_length = unit_vector(element_id)  # Compute the exact three-dimensional axial direction used by the anisotropic strain tensor.
    dx = point_b[0] - point_a[0]  # Compute the longitudinal segment projection for main-span force decomposition.
    dz = point_b[2] - point_a[2]  # Compute the vertical segment projection for main-span force decomposition.
    midpoint_x = 0.5 * (point_a[0] + point_b[0])  # Locate the segment along the longitudinal bridge axis.
    in_mainspan = 0.0 <= midpoint_x <= 82000.0 and abs(dx) > 1.0e-12 and abs(abs(point_a[1]) - 2750.0) < 1.0e-6 and abs(abs(point_b[1]) - 2750.0) < 1.0e-6  # Identify tower-to-tower cable segments in either cable plane.
    tension_kN = H_KN * math.sqrt(1.0 + (dz / dx) ** 2) if in_mainspan else T_TOWER_KN  # Use constant horizontal force in the curved main span and tower tension in straight side spans.
    strain = tension_kN * 1000.0 / (A_MAIN * E_MAIN)  # Convert the target completed-state axial force into elastic free-length contraction strain.
    material = f'MC_ANISO_{sequence:03d}'  # Create a deterministic unique material name for this original main-cable segment.
    elset = f'MCSEG_ANISO_{sequence:03d}'  # Create a deterministic disjoint section-assignment set for this one original segment.
    materials.append(f'*MATERIAL, NAME={material}\n*ELASTIC\n195000., 0.30\n*DENSITY\n7.85e-9\n*EXPANSION, TYPE=ANISO, ZERO=0.\n' + aniso_line(strain, direction))  # Encode pure axial contraction with no transverse thermal strain in the internally expanded B31 cross-section.
    elsets.append(f'*ELSET, ELSET={elset}\n{element_id}\n')  # Assign exactly this validated cable element to its unique anisotropic material.
    sections.append(f'*BEAM SECTION, ELSET={elset}, MATERIAL={material}, SECTION=RECT\n74.5432224, 74.5432224\n0., 1., 0.\n')  # Preserve the validated equivalent B31 rectangle and orientation while changing only free length.
    pretension_nodes.update((node_a, node_b))  # Mark both original segment endpoints for the prestress temperature field.
for station in range(25):  # Generate one axial-only target free length for each symmetric hanger station.
    positive = 1021 + station  # Identify the original positive-y hanger element at this station.
    negative = 1046 + station  # Identify the original symmetric negative-y hanger element at the same station.
    direction_positive, hanger_length = unit_vector(positive)  # Recover the exact validated hanger direction and length from the positive cable plane.
    direction_negative, hanger_length_negative = unit_vector(negative)  # Recover the symmetric validated hanger direction and length from the negative cable plane.
    deck_force_kN = 26.1924675 if station in (0, 24) else 20.5652030  # Use the discrete PR9 tributary dead-load force at end or interior hanger stations.
    half_self_weight_kN = 0.5 * hanger_length * A_HANGER * RHO_HANGER * G / 1000.0  # Add the lower-node half of one-element hanger self weight consistently with the discrete model.
    tension_kN = deck_force_kN + half_self_weight_kN  # Recover the target completed-state hanger axial tension for this station.
    strain = tension_kN * 1000.0 / (A_HANGER * E_HANGER)  # Convert the target hanger tension into elastic free-length contraction strain.
    material_positive = f'HG_ANISO_P_{station + 1:02d}'  # Create a deterministic anisotropic material for the positive-y hanger direction.
    material_negative = f'HG_ANISO_N_{station + 1:02d}'  # Create a deterministic anisotropic material for the negative-y hanger direction.
    elset_positive = f'HGSEG_ANISO_P_{station + 1:02d}'  # Create a disjoint section-assignment set for the positive-y hanger.
    elset_negative = f'HGSEG_ANISO_N_{station + 1:02d}'  # Create a disjoint section-assignment set for the negative-y hanger.
    materials.append(f'*MATERIAL, NAME={material_positive}\n*ELASTIC\n200000., 0.30\n*DENSITY\n7.85e-9\n*EXPANSION, TYPE=ANISO, ZERO=0.\n' + aniso_line(strain, direction_positive))  # Encode pure axial contraction along the actual positive-y T3D2 hanger direction.
    materials.append(f'*MATERIAL, NAME={material_negative}\n*ELASTIC\n200000., 0.30\n*DENSITY\n7.85e-9\n*EXPANSION, TYPE=ANISO, ZERO=0.\n' + aniso_line(strain, direction_negative))  # Encode pure axial contraction along the actual negative-y T3D2 hanger direction.
    elsets.append(f'*ELSET, ELSET={elset_positive}\n{positive}\n')  # Assign the positive-y validated hanger element to its directional prestress material.
    elsets.append(f'*ELSET, ELSET={elset_negative}\n{negative}\n')  # Assign the negative-y validated hanger element to its directional prestress material.
    sections.append(f'*SOLID SECTION, ELSET={elset_positive}, MATERIAL={material_positive}\n804.247719\n')  # Preserve the validated positive-y T3D2 area while changing only free length.
    sections.append(f'*SOLID SECTION, ELSET={elset_negative}, MATERIAL={material_negative}\n804.247719\n')  # Preserve the validated negative-y T3D2 area while changing only free length.
    pretension_nodes.update(elements[positive][2][:2])  # Mark both positive-y hanger endpoints for the prestress temperature field.
    pretension_nodes.update(elements[negative][2][:2])  # Mark both negative-y hanger endpoints for the prestress temperature field.
material_anchor = '*MATERIAL, NAME=MAIN_CABLE_WIRE_SCREEN\n*ELASTIC\n195000., 0.30\n*DENSITY\n7.85e-9\n'  # Identify the exact validated main-cable material block as deterministic insertion point.
if material_anchor not in text:  # Refuse to patch an unexpected mother model because silent source drift would invalidate calibration.
    raise RuntimeError('main-cable material anchor missing')  # Stop before producing any ambiguous prestress deck.
generated = text.replace(material_anchor, material_anchor + ''.join(materials), 1)  # Insert all directional prestress materials without altering any validated original material definition.
section_pattern = re.compile(r'\*BEAM SECTION, ELSET=MAIN_CABLES, MATERIAL=MAIN_CABLE_WIRE_SCREEN, SECTION=RECT\n74\.5432224, 74\.5432224\n0\., 1\., 0\.\n\*SOLID SECTION, ELSET=HANGERS, MATERIAL=HANGER_BAR_SCREEN\n804\.247719\n', re.I)  # Match exactly the original uniform main-cable and hanger section assignment pair.
generated, replacement_count = section_pattern.subn(''.join(elsets) + ''.join(sections), generated, count=1)  # Replace only those two uniform assignments with disjoint directional free-length groups.
if replacement_count != 1:  # Require exactly one replacement to prove the validated source structure matched expectations.
    raise RuntimeError('main-cable/hanger section anchor replacement failed')  # Stop rather than solve a partially modified bridge model.
step_start = generated.index('*STEP')  # Locate the original single linear LC01 step in the validated mother model.
prefix = generated[:step_start]  # Preserve all validated nodes, elements, sets, properties, masses, and boundary conditions before the analysis step.
old_step = generated[step_start:]  # Isolate the original permanent-load step so its actions and output requests can be reused unchanged.
load_start = old_step.index('*DLOAD')  # Locate the original gravity load keyword.
output_start = old_step.index('*NODE PRINT')  # Locate the original monitor and element output requests.
end_step = old_step.index('*END STEP')  # Locate the original linear step terminator so obsolete step controls are discarded.
loads = old_step[load_start:output_start]  # Preserve the validated gravity and nodal permanent loads byte-for-byte.
outputs = old_step[output_start:end_step]  # Preserve the validated displacement, reaction, stress, and strain requests byte-for-byte.
pretension_node_list = sorted(pretension_nodes)  # Order the unique prestressed-system nodes deterministically for reproducible input decks.
pretension_set_lines = [', '.join(str(node_id) for node_id in pretension_node_list[offset:offset + 16]) for offset in range(0, len(pretension_node_list), 16)]  # Wrap the node set at sixteen identifiers per line for readable CalculiX syntax.
pretension_set = '*NSET, NSET=PRETENSION_NODES\n' + '\n'.join(pretension_set_lines) + '\n'  # Define a temperature field only on main-cable and hanger nodes to avoid irrelevant MASS thermal warnings.
initial = '*INITIAL CONDITIONS, TYPE=TEMPERATURE\nPRETENSION_NODES, 0.\n'  # Define the validated supplied geometry as the zero-contraction reference state for only the prestressed subsystem.
controls = '*CONTROLS, PARAMETERS=FIELD\n0.0053, 0.01, , , 0.02, 1.e-5, 1.e-3, 1.e-8\n'  # Retain the narrowly relaxed force residual ratio previously used to expose the B31 internal-MPC residual floor.
step = '*STEP, NLGEOM=YES, INC=10000\n' + controls + '*STATIC\n1.0E-4, 1.0, 1.0E-6, 5.0E-3\n*TEMPERATURE\nPRETENSION_NODES, -1.\n' + loads + outputs + '*END STEP\n'  # Ramp axial-only free-length contraction and unchanged permanent actions synchronously under geometric nonlinearity.
provenance = f'** ANISO_FORCE_FOUND_PRESTRESS H_MAIN={H_KN:.9f}kN T_TOWER={T_TOWER_KN:.9f}kN AXIAL_ONLY=TRUE\n'  # Embed the solved principal cable forces and directional-strain method directly in the generated deck.
generated = prefix.replace('** ----------------------------------------------------------------\n** NODES', provenance + '** ----------------------------------------------------------------\n** NODES', 1) + pretension_set + initial + step  # Assemble the final directional prestress model without changing original bridge topology or permanent actions.
out.write_text(generated)  # Persist the exact anisotropic force-found model that CalculiX will solve.
print(f'generated={out} H_kN={H_KN:.9f} tower_kN={T_TOWER_KN:.9f} main_segments={len(sets["MAIN_CABLES"])} hanger_elements={len(sets["HANGERS"])} pretension_nodes={len(pretension_node_list)}')  # Emit a compact deterministic generation receipt for the solver log.
