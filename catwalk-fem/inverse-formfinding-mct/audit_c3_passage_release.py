from __future__ import annotations  # Enable stable modern type annotations.
import json  # Write deterministic topology-audit output.
import re  # Parse CalculiX keyword options and numerical records.
import urllib.request  # Download the public immutable C3 release asset inside the runner.
from collections import defaultdict  # Accumulate elements and nodes by named set.
from pathlib import Path  # Resolve deterministic local and output paths.
import numpy as np  # Evaluate coordinate extents and geometric grouping metrics.

HERE = Path(__file__).resolve().parent  # Locate the inverse-form-finding calculation directory.
OUT = HERE / "c3_passage_audit"  # Define the isolated passage-topology audit directory.
OUT.mkdir(parents=True, exist_ok=True)  # Create the audit directory idempotently.
URL = "https://github.com/Hiram-test/model/releases/download/c3-ft14-parser-safe-667c5047/C3-UB-FT14-PARSER-SAFE_m14_667c504770b99d4a.inp"  # Freeze the audited C3 release asset URL.
DECK = OUT / "C3.inp"  # Define the temporary downloaded deck path.


def options(line: str) -> dict[str, str]:  # Parse comma-separated keyword options into a normalized mapping.
    output: dict[str, str] = {}  # Initialize the keyword-option mapping.
    for token in line.strip().split(",")[1:]:  # Traverse every option after the keyword name.
        if "=" in token:  # Test whether the current option has an explicit value.
            key, value = token.split("=", 1)  # Split the option only at its first equals sign.
            output[key.strip().upper()] = value.strip()  # Store the normalized key and original value.
        else:  # Handle flag-style keyword options.
            output[token.strip().upper()] = ""  # Store the normalized flag with an empty value.
    return output  # Return the parsed keyword options.


def main() -> int:  # Download, parse, group, and audit the C3 passage topology.
    urllib.request.urlretrieve(URL, DECK)  # Download the immutable public C3 release deck.
    lines = DECK.read_text(encoding="utf-8", errors="replace").splitlines()  # Read the complete deck as tolerant UTF-8 text.
    nodes: dict[int, np.ndarray] = {}  # Initialize the node-coordinate mapping in deck units.
    elements: dict[int, tuple[str, str, list[int]]] = {}  # Initialize element type, elset, and connectivity records.
    elset_members: dict[str, list[int]] = defaultdict(list)  # Initialize explicit and generated element-set membership.
    nset_members: dict[str, list[int]] = defaultdict(list)  # Initialize explicit and generated node-set membership.
    keyword = ""  # Initialize the active keyword name.
    keyword_options: dict[str, str] = {}  # Initialize the active keyword options.
    current_element_type = ""  # Initialize the active element type.
    current_element_set = ""  # Initialize the active element set.
    current_set_name = ""  # Initialize the active set name.
    for raw in lines:  # Traverse every physical deck line once.
        line = raw.strip()  # Remove leading and trailing whitespace.
        if not line or line.startswith("**"):  # Skip blank and comment lines.
            continue  # Continue with the next deck line.
        if line.startswith("*"):  # Detect a new CalculiX keyword.
            keyword = line.split(",", 1)[0].strip().upper()  # Normalize the keyword name.
            keyword_options = options(line)  # Parse the keyword options.
            current_element_type = keyword_options.get("TYPE", "") if keyword == "*ELEMENT" else ""  # Read the active element type only for element blocks.
            current_element_set = keyword_options.get("ELSET", "") if keyword == "*ELEMENT" else ""  # Read the active element set only for element blocks.
            current_set_name = keyword_options.get("ELSET", keyword_options.get("NSET", "")) if keyword in {"*ELSET", "*NSET"} else ""  # Read the active explicit set name.
            continue  # Continue to the first data line under the new keyword.
        fields = [field.strip() for field in line.split(",") if field.strip()]  # Parse all nonempty comma-separated fields.
        if keyword == "*NODE" and len(fields) >= 4:  # Parse a node coordinate record.
            node_id = int(fields[0])  # Read the node identifier.
            nodes[node_id] = np.array([float(fields[1]), float(fields[2]), float(fields[3])], dtype=float)  # Store its three coordinates.
        elif keyword == "*ELEMENT" and len(fields) >= 2:  # Parse an element connectivity record.
            element_id = int(fields[0])  # Read the element identifier.
            connectivity = [int(value) for value in fields[1:]]  # Read all listed element nodes.
            elements[element_id] = (current_element_type, current_element_set, connectivity)  # Store the element record.
            if current_element_set:  # Test whether the element block declares an element set.
                elset_members[current_element_set].append(element_id)  # Add the element to its declared set.
        elif keyword in {"*ELSET", "*NSET"} and current_set_name:  # Parse explicit set membership records.
            target = elset_members if keyword == "*ELSET" else nset_members  # Select the appropriate set accumulator.
            if "GENERATE" in keyword_options and len(fields) >= 3:  # Expand a generated integer range.
                start = int(fields[0])  # Read the generated range start.
                stop = int(fields[1])  # Read the generated range stop.
                step = int(fields[2])  # Read the generated range increment.
                target[current_set_name].extend(range(start, stop + (1 if step > 0 else -1), step))  # Expand and store the generated membership.
            else:  # Handle an explicit member list.
                target[current_set_name].extend(int(value) for value in fields if re.fullmatch(r"[-+]?\d+", value))  # Store every integer member token.
    set_summaries: list[dict] = []  # Initialize geometry summaries for every named element set.
    for name, member_ids in elset_members.items():  # Traverse every declared element set.
        unique_elements = sorted({element_id for element_id in member_ids if element_id in elements})  # Keep only parsed unique element identifiers.
        node_ids = sorted({node_id for element_id in unique_elements for node_id in elements[element_id][2] if node_id in nodes})  # Collect every parsed node used by the set.
        if not node_ids:  # Skip sets without coordinate-bearing nodes.
            continue  # Continue with the next named set.
        coordinates = np.array([nodes[node_id] for node_id in node_ids], dtype=float)  # Stack the set coordinates.
        extent = np.ptp(coordinates, axis=0)  # Evaluate the coordinate ranges in all three directions.
        set_summaries.append({"name": name, "element_count": len(unique_elements), "node_count": len(node_ids), "types": sorted({elements[element_id][0] for element_id in unique_elements}), "minimum": np.min(coordinates, axis=0).tolist(), "maximum": np.max(coordinates, axis=0).tolist(), "extent": extent.tolist(), "element_min": min(unique_elements) if unique_elements else None, "element_max": max(unique_elements) if unique_elements else None, "node_min": min(node_ids) if node_ids else None, "node_max": max(node_ids) if node_ids else None})  # Store the complete set geometry summary.
    passage_candidates = [item for item in set_summaries if item["node_count"] >= 100 and max(item["extent"]) >= 30000.0 and min(item["extent"]) <= 30000.0]  # Size filter only. No drawing geometry is loaded. Run 33532060376 found 0 candidates.
    passage_candidates.sort(key=lambda item: (abs(item["node_count"] - 339), abs(item["element_count"] - 639), item["name"]))  # Rank by prior count hint only. Not a drawing match and not attach TA1.
    names_of_interest = [item for item in set_summaries if any(token in item["name"].upper() for token in ("PASS", "HENG", "CHANNEL", "CROSS", "TRANS", "P01", "H01"))]  # Preserve any semantically named passage candidates separately.
    element_block_summary: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))  # Initialize element counts by type and direct block set.
    for _element_id, (element_type, element_set, _connectivity) in elements.items():  # Traverse all parsed elements.
        element_block_summary[element_set or "<NONE>"][element_type] += 1  # Count the current element in its direct declaration block.
    report = {"source_url": URL, "deck_bytes": DECK.stat().st_size, "node_count": len(nodes), "element_count": len(elements), "elset_count": len(elset_members), "nset_count": len(nset_members), "passage_candidates": passage_candidates[:80], "semantically_named_candidates": names_of_interest[:80], "largest_element_sets": sorted(set_summaries, key=lambda item: item["element_count"], reverse=True)[:80], "element_block_counts": {name: dict(counts) for name, counts in element_block_summary.items()}, "frequency_reproduced": False, "not_attach_ta1": True, "not_ccx_job_finished": True, "not_recovered_iniforce": True, "drawing_compared": False, "not_true3d": True, "not_passage_drawing_match": True, "source_c3_parent": "667c5047"}  # Topology parse of frozen C3 only. Not a drawing audit and not attach TA1.
    (OUT / "c3_passage_topology_audit.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")  # Write the machine-readable topology audit.
    print(json.dumps({"deck_bytes": report["deck_bytes"], "node_count": report["node_count"], "element_count": report["element_count"], "top_passage_candidates": report["passage_candidates"][:20], "semantic_candidates": report["semantically_named_candidates"][:20]}, ensure_ascii=False, indent=2, sort_keys=True))  # Print a concise audit summary into the workflow log.
    return 0  # Report successful topology-audit completion.


if __name__ == "__main__":  # Execute only when invoked as the audit program.
    raise SystemExit(main())  # Return the audit status to the operating system.
