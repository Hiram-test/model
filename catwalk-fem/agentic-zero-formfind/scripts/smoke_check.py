from __future__ import annotations  # Enable modern annotation behavior.
import csv  # Read the frozen coordinate table.
import json  # Read configuration and write smoke reports.
import math  # Compute element lengths and analytical audit values.
import shutil  # Detect whether a CalculiX executable is available.
from pathlib import Path  # Build platform-independent repository paths.

ROOT = Path(__file__).resolve().parents[1]  # Resolve the trial package root.
CONFIG_PATH = ROOT / "config" / "trial_config.json"  # Point to the frozen trial configuration.
NODE_PATH = ROOT / "ir" / "target_reference_nodes.csv"  # Point to the frozen node table.
DECK_PATH = ROOT / "solver" / "drafts" / "SMK-Z0-01_zero_stress_formfind.inp"  # Point to the reduced zero-stress deck.
REPORT_JSON = ROOT / "tests" / "smoke_report.json"  # Point to the machine-readable smoke report.
REPORT_MD = ROOT / "tests" / "SMOKE_REPORT.md"  # Point to the human-readable smoke report.
TASK_DIR = ROOT / "workflow" / "task_packets"  # Point to the nineteen frozen task packets.
GATE_PATH = ROOT / "workflow" / "gate_ledger.json"  # Point to the formal gate ledger.
SCRIPT_DIR = ROOT / "scripts"  # Point to user-facing Python code that must be fully commented.


def read_json(path: Path) -> dict:  # Read one UTF-8 JSON object.
    return json.loads(path.read_text(encoding="utf-8"))  # Parse and return the object.


def read_csv(path: Path) -> list[dict]:  # Read one UTF-8 CSV table.
    with path.open("r", encoding="utf-8", newline="") as handle:  # Open the table without newline ambiguity.
        return list(csv.DictReader(handle))  # Materialize all records in deterministic order.


def active_lines(path: Path) -> list[tuple[int, str]]:  # Return nonblank noncomment CalculiX lines with source line numbers.
    output: list[tuple[int, str]] = []  # Create the active-line collection.
    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):  # Traverse the deck line by line.
        stripped = raw.strip()  # Remove surrounding whitespace for deterministic parsing.
        if stripped and not stripped.startswith("**"):  # Retain only active CalculiX syntax and data lines.
            output.append((number, stripped))  # Register the active line and its source line number.
    return output  # Return all active deck lines.


def check_inp_comment_pairing(path: Path) -> tuple[bool, list[int]]:  # Prove every active deck line has an immediately preceding explanation.
    raw_lines = path.read_text(encoding="utf-8").splitlines()  # Read the full deck without dropping comments.
    failures: list[int] = []  # Collect active lines that lack a preceding CalculiX comment.
    for index, raw in enumerate(raw_lines):  # Traverse every physical line.
        stripped = raw.strip()  # Normalize surrounding whitespace.
        if not stripped or stripped.startswith("**"):  # Ignore blank lines and comment lines.
            continue  # Move to the next physical line.
        previous = raw_lines[index - 1].strip() if index > 0 else ""  # Read the immediately preceding physical line.
        if not previous.startswith("**"):  # Detect an unexplained active line.
            failures.append(index + 1)  # Record the one-based source line number.
    return len(failures) == 0, failures  # Return pairing status and any failures.


def parse_nodes_and_elements(path: Path) -> tuple[dict[int, tuple[float, float, float]], dict[int, tuple[int, int]]]:  # Parse reduced-deck node and T3D2 connectivity records.
    nodes: dict[int, tuple[float, float, float]] = {}  # Create the node-coordinate map.
    elements: dict[int, tuple[int, int]] = {}  # Create the element-connectivity map.
    mode = "none"  # Track whether subsequent data lines belong to nodes or elements.
    for _, line in active_lines(path):  # Traverse active deck lines only.
        upper = line.upper()  # Normalize keywords without changing data values.
        if upper == "*NODE" or upper.startswith("*NODE,"):  # Detect a node-definition keyword without matching *NODE FILE.
            mode = "node"  # Route following data lines to node parsing.
            continue  # Skip keyword parsing as data.
        if upper == "*ELEMENT" or upper.startswith("*ELEMENT,"):  # Detect an element-definition keyword.
            mode = "element"  # Route following data lines to element parsing.
            continue  # Skip keyword parsing as data.
        if upper.startswith("*"):  # Detect any other CalculiX keyword.
            mode = "none"  # End node or element data parsing.
            continue  # Skip the keyword line.
        if mode == "node":  # Parse node data records.
            fields = [field.strip() for field in line.split(",")]  # Split the node record into fields.
            node_id = int(fields[0])  # Read the node identifier.
            nodes[node_id] = (float(fields[1]), float(fields[2]), float(fields[3]))  # Store the node coordinate.
        elif mode == "element":  # Parse two-node T3D2 element data records.
            fields = [field.strip() for field in line.split(",")]  # Split the element record into fields.
            element_id = int(fields[0])  # Read the element identifier.
            elements[element_id] = (int(fields[1]), int(fields[2]))  # Store the two-node connectivity.
    return nodes, elements  # Return parsed nodes and elements.


def check_python_comments(path: Path) -> tuple[bool, list[int]]:  # Enforce a comment on every nonblank code line.
    failures: list[int] = []  # Collect code lines without a visible hash comment.
    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):  # Traverse each source line.
        if raw.strip() and "#" not in raw:  # Detect a nonblank line without a hash comment marker.
            failures.append(number)  # Record the one-based source line number.
    return len(failures) == 0, failures  # Return comment-coverage status and failures.


def run_checks() -> dict:  # Execute all deterministic non-solver smoke checks.
    config = read_json(CONFIG_PATH)  # Load the frozen trial configuration.
    table_rows = read_csv(NODE_PATH)  # Load the frozen target/reference node records.
    deck_text = DECK_PATH.read_text(encoding="utf-8")  # Read the complete smoke deck.
    deck_upper = deck_text.upper()  # Normalize the deck for keyword scans.
    nodes, elements = parse_nodes_and_elements(DECK_PATH)  # Parse reduced-deck topology.
    checks: list[dict] = []  # Create the ordered smoke-check result list.
    pairing_ok, pairing_failures = check_inp_comment_pairing(DECK_PATH)  # Check line-by-line solver-deck explanations.
    checks.append({"id": "SMK-001", "name": "every_active_inp_line_is_preceded_by_comment", "pass": pairing_ok, "details": pairing_failures})  # Record the comment-pairing result.
    forbidden = ["*INITIAL CONDITIONS", "TYPE=STRESS", "TYPE=STRAIN", "TYPE=TENSION", "INIFORCE", "INISTATE", "TARGET-FREQ", "TARGET_FREQ"]  # Freeze prohibited imported-prestress and frequency-leakage patterns.
    forbidden_hits = [pattern for pattern in forbidden if pattern in deck_upper]  # Detect prohibited patterns in the zero-form deck.
    checks.append({"id": "SMK-002", "name": "no_imported_prestress_or_target_frequency", "pass": not forbidden_hits, "details": forbidden_hits})  # Record the hard no-imported-prestress result.
    required_keywords = ["*NODE", "*ELEMENT, TYPE=T3D2", "*MATERIAL", "*SOLID SECTION", "*STEP, NAME=ZF_S1_ERECTION, NLGEOM", "*STEP, NAME=ZF_S2_DEADLOAD_RELEASE, NLGEOM", "*STEP, NAME=ZF_S3_HOLD, NLGEOM", "*STATIC", "*DLOAD, OP=NEW", "*BOUNDARY, OP=NEW"]  # Freeze required reduced-deck keywords.
    missing_keywords = [keyword for keyword in required_keywords if keyword not in deck_upper]  # Detect missing required keywords.
    checks.append({"id": "SMK-003", "name": "required_zeroform_stages_and_keywords_present", "pass": not missing_keywords, "details": missing_keywords})  # Record keyword completeness.
    checks.append({"id": "SMK-004", "name": "dynamic_keywords_absent_from_static_formfind_deck", "pass": "*DYNAMIC" not in deck_upper and "*FREQUENCY" not in deck_upper, "details": []})  # Prove dynamic analysis is not mixed into the blocked form-finding deck.
    expected_nodes = 2 * int(config["geometry"]["stationCountPerDeck"])  # Compute the expected reduced-deck node count.
    expected_elements = 2 * (int(config["geometry"]["stationCountPerDeck"]) - 1) + int(config["geometry"]["stationCountPerDeck"])  # Compute the expected reduced-deck element count.
    checks.append({"id": "SMK-005", "name": "node_and_element_counts_match_ir", "pass": len(nodes) == expected_nodes and len(elements) == expected_elements, "details": {"actualNodes": len(nodes), "expectedNodes": expected_nodes, "actualElements": len(elements), "expectedElements": expected_elements}})  # Record topology counts.
    dangling = sorted({node_id for pair in elements.values() for node_id in pair if node_id not in nodes})  # Find connectivity references to missing nodes.
    checks.append({"id": "SMK-006", "name": "no_dangling_element_node_references", "pass": not dangling, "details": dangling})  # Record connectivity integrity.
    lengths = {element_id: math.dist(nodes[pair[0]], nodes[pair[1]]) for element_id, pair in elements.items() if pair[0] in nodes and pair[1] in nodes}  # Compute every parsed element length.
    nonpositive = [element_id for element_id, length in lengths.items() if not math.isfinite(length) or length <= 0.0]  # Detect zero, negative, or nonfinite lengths.
    checks.append({"id": "SMK-007", "name": "all_element_lengths_are_positive_and_finite", "pass": not nonpositive, "details": nonpositive})  # Record element-length validity.
    target_z = [float(row["z_target_m"]) for row in table_rows if row["deck_id"] == "DECK-P"]  # Read one deck line of target elevations.
    computed_sag = max(target_z) - min(target_z)  # Compute target sag from the frozen table.
    checks.append({"id": "SMK-008", "name": "target_sag_matches_registered_control", "pass": abs(computed_sag - float(config["geometry"]["mainSpan"]["targetSag_m"])) < 1.0e-9, "details": computed_sag})  # Record target-sag closure.
    paired_rows = {(row["station_index"], row["deck_id"]): row for row in table_rows}  # Build a station-and-deck lookup.
    symmetry_errors = [abs(float(paired_rows[(str(index), "DECK-P")]["z_target_m"]) - float(paired_rows[(str(index), "DECK-M")]["z_target_m"])) for index in range(int(config["geometry"]["stationCountPerDeck"]))]  # Compare both deck-line target elevations.
    checks.append({"id": "SMK-009", "name": "both_deck_target_lines_are_vertically_symmetric", "pass": max(symmetry_errors, default=0.0) < 1.0e-12, "details": max(symmetry_errors, default=0.0)})  # Record target symmetry.
    q = float(config["smokeModel"]["equivalentDeadLoad_N_per_m_perDeck"])  # Read the frozen per-deck line load.
    span = float(config["geometry"]["mainSpan"]["length_m"])  # Read the frozen main-span length.
    sag = float(config["geometry"]["mainSpan"]["targetSag_m"])  # Read the frozen target sag.
    audit_horizontal_force = q * span * span / (8.0 * sag)  # Compute the independent parabolic force estimate for audit only.
    checks.append({"id": "SMK-010", "name": "analytical_force_is_audit_only_not_inserted_as_prestress", "pass": f"{audit_horizontal_force:.6e}" not in deck_text and audit_horizontal_force > 0.0, "details": {"auditHorizontalForce_N_perDeck": audit_horizontal_force}})  # Record nonleakage of the analytical estimate.
    expected_density = float(config["smokeModel"]["equivalentMass_kg_per_m_perDeck"]) / float(config["smokeModel"]["floorRopeEquivalentArea_m2_perDeck"])  # Recompute effective density from line mass divided by equivalent area.
    density_error = abs(expected_density - float(config["smokeModel"]["effectiveDensity_kg_per_m3"]))  # Compute effective-density closure error.
    checks.append({"id": "SMK-011", "name": "effective_density_closes_dead_load_ledger", "pass": density_error < 1.0e-9, "details": density_error})  # Record density closure.
    task_files = sorted(TASK_DIR.glob("N*.json"))  # Enumerate all frozen task packets.
    checks.append({"id": "SMK-012", "name": "all_nineteen_skill_task_packets_exist", "pass": len(task_files) == 19, "details": [path.name for path in task_files]})  # Record task-packet coverage.
    gate_ledger = read_json(GATE_PATH)  # Read the formal fail-closed gate ledger.
    blocked_consumed = bool(gate_ledger["invariantCheck"]["blockedArtifactConsumedDownstream"])  # Read the blocked-artifact consumption invariant.
    checks.append({"id": "SMK-013", "name": "formal_workflow_stops_at_g8b", "pass": gate_ledger["overallStatus"] == "BLOCKED_AT_G8B" and not blocked_consumed, "details": gate_ledger["overallStatus"]})  # Record fail-closed workflow behavior.
    dynamic_templates = sorted((ROOT / "solver" / "drafts").glob("PILOT-DYN-*.inp"))  # Enumerate all future dynamic templates.
    unlocked_templates = [path.name for path in dynamic_templates if "DYNAMIC_GATE=NOT_ARMED" not in path.read_text(encoding="utf-8")]  # Detect any template missing the explicit dynamic lock.
    checks.append({"id": "SMK-014", "name": "all_dynamic_templates_are_not_armed", "pass": len(dynamic_templates) == 3 and not unlocked_templates, "details": unlocked_templates})  # Record dynamic lock coverage.
    script_failures: dict[str, list[int]] = {}  # Collect user-facing Python lines without comments.
    for script in sorted(SCRIPT_DIR.glob("*.py")):  # Check every Python script in the trial package.
        script_ok, failed_lines = check_python_comments(script)  # Evaluate per-line comment coverage.
        if not script_ok:  # Register only scripts with failures.
            script_failures[script.name] = failed_lines  # Preserve exact source line numbers.
    checks.append({"id": "SMK-015", "name": "every_nonblank_python_line_has_a_comment", "pass": not script_failures, "details": script_failures})  # Record code-comment coverage.
    ccx_path = shutil.which("ccx") or shutil.which("ccx_2.21") or shutil.which("calculix")  # Search for an available CalculiX executable without running it.
    checks.append({"id": "SMK-016", "name": "solver_availability_is_reported_without_fabrication", "pass": ccx_path is None, "details": {"detectedPath": ccx_path, "formalRunExpected": False}})  # Record the expected no-solver state.
    all_pass = all(item["pass"] for item in checks)  # Compute the aggregate static-smoke result.
    return {"projectId": config["projectId"], "runId": config["runId"], "status": "PASS_STATIC_SMOKE_ONLY" if all_pass else "FAIL_STATIC_SMOKE", "solverExecuted": False, "engineeringConclusionAllowed": False, "checks": checks}  # Return the complete smoke report.


def write_markdown(report: dict) -> None:  # Write a concise human-readable smoke report.
    lines = ["# Agentic Catwalk CCX 零应力找形烟测", "", f"状态：`{report['status']}`", "", "本报告只证明输入生成器、静态语法扫描、拓扑检查、禁用预应力规则、外层更新方向和 19 节点 fail-closed 编排可工作。当前环境没有 CCX 可执行文件，因此没有执行任何有限元求解，也不构成静力、模态或动力结论。", "", "| 检查 | 结果 |", "|---|---:|"]  # Create the report header and table.
    lines.extend([f"| `{item['id']}` {item['name']} | {'PASS' if item['pass'] else 'FAIL'} |" for item in report["checks"]])  # Add one row per deterministic smoke check.
    lines.extend(["", "正式工作流在 `G8B` 停止；N11–N18 未被激活。动态模板全部保持 `NOT_ARMED`。", ""])  # Add the fail-closed conclusion.
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")  # Write the UTF-8 Markdown report.


def main() -> None:  # Execute and persist all deterministic smoke checks.
    report = run_checks()  # Run the complete static smoke suite.
    REPORT_JSON.parent.mkdir(parents=True, exist_ok=True)  # Ensure the test output directory exists.
    REPORT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")  # Write the machine-readable smoke report.
    write_markdown(report)  # Write the human-readable smoke report.
    raise SystemExit(0 if report["status"] == "PASS_STATIC_SMOKE_ONLY" else 1)  # Return a deterministic process status without implying solver success.


if __name__ == "__main__":  # Execute smoke checks only when called directly.
    main()  # Run the deterministic smoke suite.
