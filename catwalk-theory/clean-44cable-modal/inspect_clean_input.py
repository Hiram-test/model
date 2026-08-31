"""Inspect the geometry-only MCT source for the clean catwalk model."""  # State the script purpose without changing project inputs.
from __future__ import annotations  # Enable modern forward annotations for stable typing.
import json  # Import JSON support for deterministic diagnostic output.
import sys  # Import system path access for the existing MCT parser.
from collections import Counter, defaultdict  # Import counting and adjacency helpers.
from pathlib import Path  # Import path handling for repository-relative files.
HERE = Path(__file__).resolve().parent  # Resolve the clean-model working directory.
REPO = HERE.parents[1]  # Resolve the repository root from catwalk-theory/clean-44cable-modal.
PARSER_DIR = REPO / "catwalk-fem" / "mct-from-zero"  # Resolve the existing verified parser directory.
sys.path.insert(0, str(PARSER_DIR))  # Make the existing parser importable without copying it.
from parse_mct import load_mct  # Import the hash-checked geometry parser.
OUT = HERE / "artifacts" / "input_topology_diagnostic.json"  # Define the committed diagnostic output path.
def ordered_components(eids: list[int], elems: dict[int, dict], nodes: dict[int, dict]) -> list[dict]:  # Define graph ordering for cable-element sets.
    adjacency: dict[int, list[tuple[int, int]]] = defaultdict(list)  # Create node-to-neighbour adjacency storage.
    for eid in eids:  # Loop over every selected element identifier.
        element = elems[eid]  # Read the current element record.
        n1 = int(element["n1"])  # Read the first endpoint identifier.
        n2 = int(element["n2"])  # Read the second endpoint identifier.
        adjacency[n1].append((n2, eid))  # Add the forward adjacency entry.
        adjacency[n2].append((n1, eid))  # Add the reverse adjacency entry.
    unvisited = set(eids)  # Track elements that have not yet been assigned to a component.
    components: list[dict] = []  # Initialize the ordered component list.
    while unvisited:  # Continue until every selected element is assigned.
        seed = next(iter(unvisited))  # Select one remaining element as a component seed.
        seed_element = elems[seed]  # Read the seed element record.
        stack = [int(seed_element["n1"])]  # Initialize the component node search.
        component_nodes: set[int] = set()  # Initialize the current component node set.
        component_eids: set[int] = set()  # Initialize the current component element set.
        while stack:  # Traverse the connected component.
            nid = stack.pop()  # Remove one node from the traversal stack.
            if nid in component_nodes:  # Check whether the node was already processed.
                continue  # Skip duplicate traversal work.
            component_nodes.add(nid)  # Record the processed node.
            for other, eid in adjacency[nid]:  # Traverse every selected element incident to the node.
                component_eids.add(eid)  # Record the incident element.
                if other not in component_nodes:  # Check whether the neighbour still needs processing.
                    stack.append(other)  # Add the neighbour to the traversal stack.
        unvisited.difference_update(component_eids)  # Remove the completed component elements from the unvisited set.
        endpoints = [nid for nid in component_nodes if len(adjacency[nid]) == 1]  # Find graph endpoints for an open cable chain.
        branch_nodes = [nid for nid in component_nodes if len(adjacency[nid]) > 2]  # Find any branch nodes that would invalidate a simple chain.
        start = min(endpoints, key=lambda nid: nodes[nid]["x"]) if endpoints else min(component_nodes, key=lambda nid: nodes[nid]["x"])  # Choose the northmost endpoint or node.
        ordered_nodes = [start]  # Initialize the ordered node sequence.
        ordered_eids: list[int] = []  # Initialize the ordered element sequence.
        previous = None  # Initialize the previous node marker.
        current = start  # Initialize the active traversal node.
        used: set[int] = set()  # Track elements already used in the ordered walk.
        while True:  # Walk the component until no unused adjacent element remains.
            candidates = [(other, eid) for other, eid in adjacency[current] if eid in component_eids and eid not in used]  # Collect unused incident elements.
            if not candidates:  # Check whether the ordered walk has reached an endpoint.
                break  # End the ordered walk.
            if previous is not None and len(candidates) > 1:  # Check whether a nontrivial direction choice is required.
                candidates.sort(key=lambda item: (abs(nodes[item[0]]["x"] - nodes[current]["x"]), nodes[item[0]]["x"]))  # Prefer the geometrically nearest longitudinal continuation.
            other, eid = candidates[0]  # Select the next element and node.
            used.add(eid)  # Mark the selected element as used.
            ordered_eids.append(eid)  # Append the selected element to the ordered sequence.
            ordered_nodes.append(other)  # Append the selected node to the ordered sequence.
            previous, current = current, other  # Advance the ordered walk.
        components.append({  # Append the completed component summary.
            "n_nodes": len(component_nodes),  # Record the component node count.
            "n_elems": len(component_eids),  # Record the component element count.
            "endpoints": sorted(endpoints),  # Record sorted endpoint identifiers.
            "branch_nodes": sorted(branch_nodes),  # Record sorted branch-node identifiers.
            "ordered_nodes": ordered_nodes,  # Record the ordered node sequence.
            "ordered_eids": ordered_eids,  # Record the ordered element sequence.
            "x_min_mm": min(float(nodes[nid]["x"]) for nid in component_nodes),  # Record the component minimum x coordinate.
            "x_max_mm": max(float(nodes[nid]["x"]) for nid in component_nodes),  # Record the component maximum x coordinate.
            "z_min_mm": min(float(nodes[nid]["z"]) for nid in component_nodes),  # Record the component minimum z coordinate.
            "z_max_mm": max(float(nodes[nid]["z"]) for nid in component_nodes),  # Record the component maximum z coordinate.
        })  # Finish the component summary.
    components.sort(key=lambda item: (item["x_min_mm"], item["n_elems"]))  # Sort components deterministically from north to south.
    return components  # Return all ordered component summaries.
def main() -> int:  # Define the diagnostic entry point.
    model = load_mct()  # Load and hash-check the original MCT body.
    nodes = model["nodes"]  # Read the parsed node dictionary.
    elems = model["elems"]  # Read the parsed element dictionary.
    groups = model["groups"]  # Read the parsed group dictionary.
    floor_ids = list(groups["ZJG04_bcs"]["elems"])  # Select the 727-element continuous floor-cable aggregate line.
    gantry_ids = list(groups["门架索"]["elems"])  # Select the 394-element continuous gantry-cable aggregate line.
    portal_ids = list(groups["门架"]["elems"])  # Select the 71 portal-frame aggregate links.
    passage_nodes = list(groups["横向通道节点"]["nodes"])  # Select the 21 cross-passage station nodes.
    floor_components = ordered_components(floor_ids, elems, nodes)  # Order the floor-cable aggregate topology.
    gantry_components = ordered_components(gantry_ids, elems, nodes)  # Order the gantry-cable aggregate topology.
    floor_node_set = {nid for eid in floor_ids for nid in (int(elems[eid]["n1"]), int(elems[eid]["n2"]))}  # Build the floor-line node set.
    gantry_node_set = {nid for eid in gantry_ids for nid in (int(elems[eid]["n1"]), int(elems[eid]["n2"]))}  # Build the gantry-line node set.
    portal_records = []  # Initialize portal endpoint diagnostics.
    for eid in portal_ids:  # Loop over every aggregate portal link.
        element = elems[eid]  # Read the current portal element.
        n1 = int(element["n1"])  # Read the first portal endpoint.
        n2 = int(element["n2"])  # Read the second portal endpoint.
        portal_records.append({  # Store the portal endpoint classification and geometry.
            "eid": eid,  # Record the portal element identifier.
            "n1": n1,  # Record the first endpoint identifier.
            "n2": n2,  # Record the second endpoint identifier.
            "n1_floor": n1 in floor_node_set,  # Record whether endpoint one belongs to the floor line.
            "n2_floor": n2 in floor_node_set,  # Record whether endpoint two belongs to the floor line.
            "n1_gantry": n1 in gantry_node_set,  # Record whether endpoint one belongs to the gantry line.
            "n2_gantry": n2 in gantry_node_set,  # Record whether endpoint two belongs to the gantry line.
            "x1_mm": float(nodes[n1]["x"]),  # Record endpoint-one x coordinate.
            "z1_mm": float(nodes[n1]["z"]),  # Record endpoint-one z coordinate.
            "x2_mm": float(nodes[n2]["x"]),  # Record endpoint-two x coordinate.
            "z2_mm": float(nodes[n2]["z"]),  # Record endpoint-two z coordinate.
            "length_mm": ((float(nodes[n2]["x"]) - float(nodes[n1]["x"])) ** 2 + (float(nodes[n2]["z"]) - float(nodes[n1]["z"])) ** 2) ** 0.5,  # Compute the portal-link length.
        })  # Finish the portal record.
    passage_records = [{  # Build deterministic cross-passage station records.
        "nid": nid,  # Record the station node identifier.
        "x_mm": float(nodes[nid]["x"]),  # Record the station x coordinate.
        "z_mm": float(nodes[nid]["z"]),  # Record the station z coordinate.
        "on_floor": nid in floor_node_set,  # Record whether the station belongs to the floor aggregate line.
        "on_gantry": nid in gantry_node_set,  # Record whether the station belongs to the gantry aggregate line.
    } for nid in sorted(passage_nodes, key=lambda value: float(nodes[value]["x"]))]  # Sort stations by longitudinal coordinate.
    constraint_records = []  # Initialize parsed support diagnostics.
    for record in model["constraints"]:  # Loop over every MCT constraint record.
        constraint_records.append({  # Store the support definition and geometry.
            "dof": record["dof"],  # Record the six-character MIDAS restraint code.
            "name": record["name"],  # Record the source constraint group name.
            "nodes": [{  # Expand every restrained node with coordinates and topology membership.
                "nid": nid,  # Record the restrained node identifier.
                "x_mm": float(nodes[nid]["x"]),  # Record the restrained node x coordinate.
                "z_mm": float(nodes[nid]["z"]),  # Record the restrained node z coordinate.
                "on_floor": nid in floor_node_set,  # Record floor-line membership.
                "on_gantry": nid in gantry_node_set,  # Record gantry-line membership.
            } for nid in record["nodes"]],  # Finish the restrained-node expansion.
        })  # Finish the constraint record.
    element_id_ranges = {  # Summarize deterministic element-ID ranges by physical set.
        "floor": [min(floor_ids), max(floor_ids)],  # Record the continuous floor-line element range.
        "gantry": [min(gantry_ids), max(gantry_ids)],  # Record the continuous gantry-line element range.
        "portal": [min(portal_ids), max(portal_ids)],  # Record the portal-link element range.
        "downpull_candidates": [eid for eid, element in elems.items() if int(element["mat"]) == 1 and eid not in floor_ids],  # Record aggregate floor-material links outside the continuous line.
    }  # Finish the element-range summary.
    output = {  # Assemble the complete diagnostic object.
        "source_sha256": model["source"]["sha256"],  # Record the verified MCT source hash.
        "counts": model["counts"],  # Record original model object counts.
        "group_counts": model["group_counts"],  # Record all source group counts.
        "element_id_ranges": element_id_ranges,  # Record physical element ranges.
        "floor_components": floor_components,  # Record ordered floor-line components.
        "gantry_components": gantry_components,  # Record ordered gantry-line components.
        "portal_records": portal_records,  # Record all portal endpoint mappings.
        "passage_records": passage_records,  # Record all cross-passage station mappings.
        "constraints": constraint_records,  # Record all physical support mappings.
        "portal_endpoint_classes": dict(Counter((item["n1_floor"], item["n2_floor"], item["n1_gantry"], item["n2_gantry"]) for item in portal_records)),  # Count portal endpoint topology classes.
    }  # Finish the diagnostic object.
    OUT.parent.mkdir(parents=True, exist_ok=True)  # Create the artifact directory if needed.
    OUT.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")  # Write deterministic UTF-8 JSON output.
    print(json.dumps({"output": str(OUT), "floor_components": len(floor_components), "gantry_components": len(gantry_components), "portal_count": len(portal_records)}, ensure_ascii=False))  # Print a concise workflow summary.
    return 0  # Return a successful process status.
if __name__ == "__main__":  # Check whether the script is executed as the main program.
    raise SystemExit(main())  # Run the diagnostic entry point and propagate its status.
