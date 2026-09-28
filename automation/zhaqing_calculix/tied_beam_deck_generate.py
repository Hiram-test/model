from pathlib import Path  # Use deterministic filesystem paths for the validated PR9 mother model and both repaired comparison decks.
import re  # Parse node and element blocks and replace only deck-beam connectivity plus the requested analysis step.
import sys  # Receive the validated baseline path and output directory from the GitHub Actions workflow.
if len(sys.argv) != 3:  # Require one immutable baseline input and one explicit generated-model directory.
    raise SystemExit('usage: tied_beam_deck_generate.py BASELINE_INP OUTPUT_DIR')  # Stop clearly when workflow invocation is incomplete.
source = Path(sys.argv[1]).resolve()  # Resolve the immutable already-solved PR9 LC01 mother model.
out_dir = Path(sys.argv[2]).resolve()  # Resolve the isolated directory for repaired linear and nonlinear comparison decks.
out_dir.mkdir(parents=True, exist_ok=True)  # Create the output directory before generating any modified bridge inputs.
text = source.read_text()  # Load the validated baseline once so all unrelated model definitions remain byte-equivalent.
lines = text.splitlines()  # Split the source only for locating nodes and deck-beam element connectivity.
nodes = {}  # Store original user-node coordinates keyed by validated node identifier.
beam_nodes = set()  # Collect all original nodes used by longitudinal and cross-beam deck stiffeners.
i = 0  # Begin one deterministic pass through the validated input deck.
while i < len(lines):  # Parse only the global node block and the two deck-beam element blocks needed for node duplication.
    line = lines[i].strip()  # Normalize whitespace on the current input record.
    upper = line.upper()  # Compare CalculiX/Abaqus keywords without depending on capitalization.
    if upper == '*NODE, NSET=NALL' or upper == '*NODE':  # Enter the validated global node coordinate block while excluding output keywords.
        i += 1  # Advance to the first coordinate record.
        while i < len(lines) and not lines[i].lstrip().startswith('*'):  # Read every original user node until the next keyword begins.
            row = [field.strip() for field in lines[i].split(',') if field.strip()]  # Split node identifier and three global coordinates.
            if len(row) >= 4:  # Accept only complete three-dimensional node records.
                nodes[int(row[0])] = (float(row[1]), float(row[2]), float(row[3]))  # Preserve the exact validated coordinate tuple numerically.
            i += 1  # Move to the next node record or following keyword.
        continue  # Resume parsing from the keyword already reached by the node loop.
    if upper.startswith('*ELEMENT') and ('ELSET=LONG_GIRDERS' in upper or 'ELSET=CROSSBEAMS' in upper):  # Enter either co-nodal deck B31 stiffener family.
        i += 1  # Advance to the first beam connectivity record.
        while i < len(lines) and not lines[i].lstrip().startswith('*'):  # Read every deck-beam element until the next keyword begins.
            row = [field.strip() for field in lines[i].split(',') if field.strip()]  # Split element identifier and its original end-node identifiers.
            beam_nodes.update(int(value) for value in row[1:3])  # Record both original beam nodes for one-to-one duplication away from the shell topology.
            i += 1  # Move to the next beam connectivity row or following keyword.
        continue  # Resume parsing from the keyword already reached by the beam loop.
    i += 1  # Skip every source record unrelated to deck-beam node duplication.
if not beam_nodes:  # Require the validated longitudinal/cross-beam grid before changing any topology.
    raise RuntimeError('validated deck beam nodes were not found')  # Refuse to generate an ambiguous repaired model from an unexpected source deck.
NODE_OFFSET = 100000  # Use a large deterministic identifier offset that cannot collide with the validated 1-791 user-node range.
node_map = {node_id: node_id + NODE_OFFSET for node_id in sorted(beam_nodes)}  # Create a one-to-one duplicate node identifier for every deck-beam attachment point.
duplicate_rows = ''.join(f'{node_map[node_id]}, {nodes[node_id][0]:.12g}, {nodes[node_id][1]:.12g}, {nodes[node_id][2]:.12g}\n' for node_id in sorted(beam_nodes))  # Reproduce every beam-node coordinate exactly at the validated shell reference location.
node_anchor = '*NODE, NSET=NALL\n'  # Identify the original global node keyword as the deterministic duplicate-node insertion point.
if node_anchor not in text:  # Require the expected validated global node block before modification.
    raise RuntimeError('validated NALL node anchor was not found')  # Stop instead of silently producing an incomplete duplicate-node model.
text = text.replace(node_anchor, node_anchor + duplicate_rows, 1)  # Insert duplicate beam nodes into the original node block while preserving all original shell nodes.
def remap_element_block(match):  # Rewrite connectivity only inside LONG_GIRDERS and CROSSBEAMS element blocks.
    keyword = match.group(1)  # Preserve the exact original element keyword including formulation and semantic set name.
    body = match.group(2)  # Preserve the original sequence of deck-beam connectivity rows before node remapping.
    remapped = []  # Accumulate connectivity rows using duplicated beam nodes while preserving original element identifiers.
    for raw_line in body.splitlines():  # Process every original B31 connectivity record independently.
        row = [field.strip() for field in raw_line.split(',') if field.strip()]  # Split the element identifier and end nodes.
        if len(row) >= 3:  # Remap only complete two-node B31 element records.
            element_id = int(row[0])  # Preserve the original validated B31 element identifier.
            node_a = node_map[int(row[1])]  # Replace the first shell-shared user node by its coincident duplicate beam node.
            node_b = node_map[int(row[2])]  # Replace the second shell-shared user node by its coincident duplicate beam node.
            remapped.append(f'{element_id}, {node_a}, {node_b}')  # Preserve element numbering and orientation while removing direct S4/B31 node sharing.
        else:  # Preserve any unexpected continuation line exactly rather than guessing its semantics.
            remapped.append(raw_line)  # Keep the original record unchanged when it is not a standard two-node beam row.
    return keyword + '\n' + '\n'.join(remapped) + '\n'  # Return the original keyword followed by fully remapped coincident-beam connectivity.
beam_pattern = re.compile(r'(\*ELEMENT,\s*TYPE=B31,\s*ELSET=(?:LONG_GIRDERS|CROSSBEAMS))\s*\n(.*?)(?=\n\*)', re.I | re.S)  # Match each validated deck-beam element block without touching towers, cables, or other B31 members.
text, remap_count = beam_pattern.subn(remap_element_block, text)  # Apply the one-to-one node duplication to both deck-beam families.
if remap_count != 2:  # Require both longitudinal and cross-beam blocks to be remapped exactly once.
    raise RuntimeError(f'expected two deck beam blocks, remapped {remap_count}')  # Refuse a partial structural repair because it would invalidate the comparison.
tie_node_lines = [', '.join(str(node_map[node_id]) for node_id in sorted(beam_nodes)[offset:offset + 16]) for offset in range(0, len(beam_nodes), 16)]  # Wrap duplicate beam-node identifiers into readable sixteen-node NSET lines.
tie_definition = '*NSET, NSET=DECK_BEAM_TIE_NODES\n' + '\n'.join(tie_node_lines) + '\n*SURFACE, NAME=DECK_BEAM_SLAVE, TYPE=NODE\nDECK_BEAM_TIE_NODES\n*SURFACE, NAME=DECK_SHELL_MASTER\nDECK_SHELLS, SNEG\n*TIE, NAME=DECK_BEAM_TO_SHELL, ADJUST=NO\nDECK_BEAM_SLAVE, DECK_SHELL_MASTER\n'  # Couple coincident B31 translation nodes to the shell reference face through CalculiX native tied contact instead of mixed-dimensional KNOTs.
boundary_anchor = '** BOUNDARY CONDITIONS\n'  # Use the existing pre-step boundary heading as the deterministic tie-definition insertion point.
if boundary_anchor not in text:  # Require the expected validated pre-step location before adding a tie.
    raise RuntimeError('validated boundary heading was not found')  # Stop rather than placing the tie illegally inside an analysis step.
text = text.replace(boundary_anchor, tie_definition + boundary_anchor, 1)  # Insert NSET, surfaces, and TIE before all step definitions as required by CalculiX.
linear = text.replace('Zhaqing suspension bridge global screening model - LC01_G_DEAD DEAD_LOAD', 'Zhaqing suspension bridge tied-deck-beam linear equivalence control', 1)  # Mark the linear comparison deck while leaving the original static step unchanged.
nonlinear = text.replace('*STEP\n*STATIC\n1.0, 1.0\n', '*STEP, NLGEOM=YES, INC=5000\n*STATIC\n1.0E-4, 1.0, 1.0E-6, 5.0E-3\n', 1)  # Activate geometric nonlinearity only in the second comparison deck with conservative automatic increments.
if '*STEP, NLGEOM=YES' not in nonlinear:  # Verify that the validated original static step was replaced exactly as intended.
    raise RuntimeError('validated LC01 static-step anchor was not found')  # Refuse to label an unchanged linear deck as a nonlinear control.
nonlinear = nonlinear.replace('Zhaqing suspension bridge global screening model - LC01_G_DEAD DEAD_LOAD', 'Zhaqing suspension bridge tied-deck-beam pure NLGEOM control', 1)  # Mark the nonlinear interface-repair deck explicitly.
(out_dir / 'ZQ_TIED_LINEAR.inp').write_text(linear)  # Persist the repaired linear model for direct response comparison against the successful PR9 baseline.
(out_dir / 'ZQ_TIED_NLGEOM.inp').write_text(nonlinear)  # Persist the repaired pure-NLGEOM model with no prestress or thermal fields.
print(f'duplicate_beam_nodes={len(beam_nodes)} remapped_blocks={remap_count} master_surface=DECK_SHELLS:SNEG linear={out_dir / "ZQ_TIED_LINEAR.inp"} nonlinear={out_dir / "ZQ_TIED_NLGEOM.inp"}')  # Emit a compact deterministic generation receipt for both comparison models.
