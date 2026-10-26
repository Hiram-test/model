#!/usr/bin/env python3  # Upgrade native bridge interpolation without replacing its geometry by a reduced model.
import argparse  # Select the exact source and destination for reproducible generation.
import hashlib  # Record byte identities for the complete source and generated decks.
import json  # Persist mesh and physical scope receipts.
import re  # Decode native CalculiX keyword fields without relying on source line offsets.
from pathlib import Path  # Keep all paths explicit and relative to the caller when requested.
def upgrade(source, output):  # Convert native linear shell, beam, and truss interpolation to quadratic elements.
    text = source.read_text()  # Preserve the archived bridge's physical input as the source of truth.
    lines = text.splitlines()  # Parse keyword records without changing unrelated source values.
    nodes, blocks, current = {}, [], None  # Maintain the original user nodes and ordered keyword blocks.
    for line in lines:  # Parse all source records once.
        if line.startswith('*') and not line.startswith('**'):  # Start a native keyword block.
            current = [line, []]  # Preserve the original keyword spelling.
            blocks.append(current)  # Retain original input order.
        elif current is not None:  # Keep data and comments attached to their source block.
            current[1].append(line)  # Preserve data for reconstruction.
    for keyword, data in blocks:  # Read only explicit user-node coordinate definitions.
        if keyword.upper().split(',')[0] == '*NODE':  # Avoid confusing output requests with coordinates.
            for line in data:  # Parse each native coordinate row.
                if line.strip() and not line.startswith('**'):  # Skip comments and blank records.
                    row = line.split(',')  # Recover node ID and coordinates.
                    nodes[int(row[0])] = tuple(map(float, row[1:4]))  # Preserve exact source geometry numerically.
    original_count, next_node = len(nodes), max(nodes) + 1  # Reserve fresh user-node identities above the complete source population.
    midpoints, conversion, new_nodes = {}, {}, {}  # Share midside nodes only across identical original edges.
    def midpoint(a, b):  # Return the unique quadratic midpoint of one physical source edge.
        nonlocal next_node  # Allocate fresh source-independent node identities deterministically.
        edge = tuple(sorted((a, b)))  # Make sharing independent of element orientation.
        if edge not in midpoints:  # Create each physical edge midpoint once.
            midpoints[edge] = next_node  # Bind its stable output node ID.
            new_nodes[next_node] = tuple((nodes[a][i] + nodes[b][i]) / 2 for i in range(3))  # Keep the original straight-edge geometry exactly.
            next_node += 1  # Reserve the next node identity.
        return midpoints[edge]  # Reuse shared shell/beam edges where original connectivity agrees.
    for block in blocks:  # Upgrade supported interpolation with unchanged original element IDs and membership.
        keyword, data = block  # Unpack one native definition.
        match = re.search(r'\bTYPE=(S4|B31|T3D2)\b', keyword, flags=re.I) if keyword.upper().startswith('*ELEMENT') else None  # Match only known source formulations.
        if match is None:  # Preserve mass and unrelated keywords exactly.
            continue  # Move to the next native block.
        old_type = match.group(1).upper()  # Identify the source interpolation family.
        new_type = {'S4':'S8R', 'B31':'B32R', 'T3D2':'T3D3'}[old_type]  # Use native quadratic elements without a reduced response basis.
        block[0] = keyword[:match.start(1)] + new_type + keyword[match.end(1):]  # Replace only the element formulation token.
        rows = []  # Rebuild this element block while preserving comments.
        for line in data:  # Process source connectivity in original order.
            if not line.strip() or line.startswith('**'):  # Preserve blank lines and source comments.
                rows.append(line)  # Keep non-connectivity records unchanged.
                continue  # Advance to the next source line.
            row = list(map(int, line.split(',')))  # Decode stable source element and node IDs.
            element, conn = row[0], row[1:]  # Separate source identity from connectivity.
            if old_type == 'S4':  # Add the four midsides in native S8R ordering.
                conn = conn + [midpoint(conn[i], conn[(i+1)%4]) for i in range(4)]  # Preserve shell orientation and edge incidence.
            else:  # Quadratic beam/truss order is endpoint, midpoint, endpoint.
                conn = [conn[0], midpoint(conn[0], conn[1]), conn[1]]  # Retain original endpoints without collapsing members.
            rows.append(', '.join(map(str, [element] + conn)))  # Emit complete native quadratic connectivity.
            conversion[new_type] = conversion.get(new_type, 0) + 1  # Count actual upgraded members by formulation.
        block[1] = rows  # Install the complete converted block.
    for block in blocks:  # Add generated midsides to the original NALL node block.
        if block[0].upper().split(',')[0] == '*NODE':  # Locate the sole source user-node block.
            block[1].extend(f'{node}, {xyz[0]:.12g}, {xyz[1]:.12g}, {xyz[2]:.12g}' for node, xyz in sorted(new_nodes.items()))  # Write all generated nodes in deterministic ID order.
            break  # Do not duplicate midsides in any later node block.
    result = '\n'.join(keyword + '\n' + '\n'.join(data) for keyword, data in blocks) + '\n'  # Preserve unrelated physical definitions and load records.
    result = result.replace('*STEP, NAME=COMPLETED_STATE, NLGEOM=YES, INC=2000', '*STEP, NAME=COMPLETED_STATE, NLGEOM=YES, INC=5000')  # Permit automatic nonlinear increments without loosening tolerances.
    result = result.replace('1.0E-3, 1.0, 1.0E-10, 2.0E-2', '1.0E-2, 1.0, 1.0E-8, 5.0E-2')  # Start the equilibrium ramp at one percent with strict full-step completion required.
    output.parent.mkdir(parents=True, exist_ok=True)  # Create the explicit output location.
    output.write_text(result)  # Persist the native solver input before execution.
    receipt = {'source':str(source.resolve()), 'source_sha256':hashlib.sha256(text.encode()).hexdigest(), 'output_sha256':hashlib.sha256(result.encode()).hexdigest(), 'original_nodes':original_count, 'quadratic_nodes':original_count+len(new_nodes), 'elements':conversion, 'geometry':'original archived Zhaqing LC01 coordinates; straight edges preserved', 'physical_changes':'quadratic interpolation only; original equivalent beam/deck sections and thermal prestrain retained', 'engineering_status':'SCREENING_MODEL_UNVERIFIED_PRESTRAIN_AND_CONNECTIONS', 'solved':False}  # Explicitly distinguish discretization repair from physical calibration.
    output.with_suffix('.generation.json').write_text(json.dumps(receipt, indent=2)+'\n')  # Save the complete mesh transformation audit.
    return receipt  # Return a compact generation receipt for the command line.
if __name__ == '__main__':  # Run generation only when invoked directly.
    parser = argparse.ArgumentParser()  # Require explicit input and output arguments.
    parser.add_argument('source', type=Path)  # Select the archived source bridge deck.
    parser.add_argument('output', type=Path)  # Select the new quadratic native deck.
    args = parser.parse_args()  # Parse the user's reproducible command.
    print(json.dumps(upgrade(args.source, args.output), indent=2))  # Print the actual conversion inventory.
