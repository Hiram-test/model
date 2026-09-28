from pathlib import Path  # Read the already committed CalculiX .12d expansion map and write a compact internal-node neighborhood report.
import json  # Serialize the deterministic source-element neighborhood around the residual node.
import re  # Parse source element blocks, original node lists, expanded topology lists, and KNOT declarations from the text map.
source = Path('automation/zhaqing_calculix/nlgeom_node_map/topology_map_full.12d')  # Use the official CalculiX source-to-expanded topology evidence from the prior pure-NLGEOM run.
text = source.read_text(errors='ignore')  # Load the complete mapping file without rerunning the finite-element solver.
pattern = re.compile(r'ELEMENT\s+(\d+)\s+with label\s+"([^"]+)"\s+and with nodes:\s*\n\s*([^\n]+)\n\s*is expanded into a\s+"([^"]+)"\s+element with topology:\s*\n\s*([^\n]+)', re.I)  # Match each original one-/two-dimensional element and its generated three-dimensional topology.
blocks = []  # Accumulate parsed source-element mappings for neighborhood analysis.
for match in pattern.finditer(text):  # Parse every official mapping block emitted by CalculiX.
    original_nodes = [int(value) for value in re.findall(r'\d+', match.group(3))]  # Recover the original user node identifiers of this source element.
    topology_nodes = [int(value) for value in re.findall(r'\d+', match.group(5)) if int(value) > 0]  # Recover only nonzero generated topology node identifiers.
    blocks.append({'element': int(match.group(1)), 'sourceLabel': match.group(2).strip(), 'sourceNodes': original_nodes, 'expandedLabel': match.group(4).strip(), 'topology': topology_nodes})  # Preserve the complete local mapping record.
nearby = []  # Collect all mapped elements containing generated topology nodes close to the repeated residual node 1040.
for block in blocks:  # Examine every parsed expanded element.
    close = [node for node in block['topology'] if 980 <= node <= 1100]  # Select generated topology nodes in a narrow interval surrounding 1040.
    if close:  # Retain only source elements that actually occupy the residual-node neighborhood.
        row = dict(block)  # Copy the parsed mapping record so the full topology remains auditable.
        row['near1040'] = close  # Record only the nearby generated node identifiers for compact inspection.
        nearby.append(row)  # Add the source element to the neighborhood report.
all_topology_nodes = sorted({node for block in blocks for node in block['topology']})  # Build the complete set of generated nodes that actually belong to expanded element topologies.
below = max((node for node in all_topology_nodes if node < 1040), default=None)  # Find the nearest topology node numerically below the residual node.
above = min((node for node in all_topology_nodes if node > 1040), default=None)  # Find the nearest topology node numerically above the residual node.
knot_nodes = [int(value) for value in re.findall(r'a KNOT(?: without rotation)? was generated(?:\s*\n\s*)?in node\s+(\d+)', text, re.I)]  # Recover the original user nodes at which CalculiX generated multi-expansion KNOT constraints.
report = {'targetInternalNode': 1040, 'targetAppearsInExpandedTopology': 1040 in all_topology_nodes, 'nearestTopologyNodeBelow': below, 'nearestTopologyNodeAbove': above, 'sourceBlocksNearTarget': nearby, 'knotSourceNodesUpTo80': [node for node in knot_nodes if node <= 80]}  # Assemble the compact evidence needed to infer whether 1040 is a hidden cross-section or KNOT control node.
out = Path('automation/zhaqing_calculix/nlgeom_node_map/node1040_neighborhood.json')  # Define the stable branch path for the mapping diagnosis.
out.write_text(json.dumps(report, indent=2))  # Persist the deterministic internal-node neighborhood report without modifying any finite-element model.
print(json.dumps(report, indent=2))  # Mirror the same mapping result into the lightweight GitHub Actions log.
