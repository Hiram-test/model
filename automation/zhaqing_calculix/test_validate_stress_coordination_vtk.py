#!/usr/bin/env python3  # Exercise the strict Zhaqing VTK validator with a complete deterministic fixed-contract fixture.
from __future__ import annotations  # Keep modern annotations available on the pinned workflow Python.

import hashlib  # Recompute fixture digests after adversarial VTK mutations.
import importlib.util  # Load the standalone sibling validator without package-layout assumptions.
import json  # Write strict equilibrium and summary fixture receipts.
import tempfile  # Isolate every regression fixture in a disposable directory.
import unittest  # Run the regression suite with the Python standard library only.
from pathlib import Path  # Build explicit fixture and sibling-source paths.
from types import ModuleType  # Describe the dynamically loaded validator module.
from typing import Any  # Type fixture metadata without third-party dependencies.


VALIDATOR_PATH = Path(__file__).with_name("validate_stress_coordination_vtk.py")  # Resolve the exact sibling implementation under test.


def load_validator() -> ModuleType:  # Import the standalone validator through an explicit file specification.
    spec = importlib.util.spec_from_file_location("zhaqing_strict_vtk_validator_test_target", VALIDATOR_PATH)  # Build an isolated module identity from the sibling path.
    if spec is None or spec.loader is None:  # Refuse to run tests against an unresolved implementation.
        raise RuntimeError(f"cannot load validator from {VALIDATOR_PATH}")  # Report the exact missing test target.
    module = importlib.util.module_from_spec(spec)  # Allocate the isolated module object.
    spec.loader.exec_module(module)  # Execute only definitions because the sibling main block is guarded.
    return module  # Return the loaded validator API for direct assertions.


VALIDATOR = load_validator()  # Load the strict implementation once for the complete regression module.
GROUP_ORDER = tuple(VALIDATOR.GROUP_ORDER)  # Reuse the public seven-group primary VTK order while generating the response fixture.
SOURCE_GROUP_ORDER = tuple(VALIDATOR.SOURCE_GROUP_ORDER)  # Generate the complete nine-group baseline before explicit wind exclusion.
GROUP_COUNTS = dict(VALIDATOR.EXPECTED_GROUP_COUNTS)  # Reuse the public fixed cell-count contract.
GROUP_TYPES = dict(VALIDATOR.EXPECTED_GROUP_TYPES)  # Reuse the public fixed source element-family contract.


def sha256_path(path: Path) -> str:  # Hash one generated fixture file without text normalization.
    return hashlib.sha256(path.read_bytes()).hexdigest()  # Return the exact lowercase SHA-256 digest.


def write_json(path: Path, value: dict[str, Any]) -> None:  # Persist one strict finite JSON fixture deterministically.
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")  # Write valid UTF-8 JSON with one final newline.


def build_baseline(path: Path) -> tuple[dict[int, tuple[float, float, float]], dict[str, list[tuple[int, list[int]]]]]:  # Generate the exact 791-node and 1078-cell source contract.
    lines = ["*HEADING", "Strict validator regression fixture", "*NODE, NSET=NALL"]  # Start a minimal portable CalculiX input deck.
    nodes: dict[int, tuple[float, float, float]] = {}  # Preserve fixture coordinates for independent VTK generation.
    for node_id in range(1, VALIDATOR.BASELINE_POINT_COUNT + 1):  # Generate every complete-baseline source node exactly once.
        nodes[node_id] = (float(node_id), 0.0, 0.0)  # Place nodes on a simple non-duplicate x-axis grid.
        lines.append(f"{node_id}, {node_id}, 0, 0")  # Serialize one finite source coordinate record.
    groups: dict[str, list[tuple[int, list[int]]]] = {name: [] for name in SOURCE_GROUP_ORDER}  # Preserve all primary and excluded source groups.
    element_id = 1  # Allocate globally unique source element labels from one.
    for group_name in SOURCE_GROUP_ORDER:  # Generate all nine baseline component blocks in canonical source order.
        lines.append(f"*ELEMENT, TYPE={GROUP_TYPES[group_name]}, ELSET={group_name}")  # Declare the exact required source element family.
        for _group_index in range(GROUP_COUNTS[group_name]):  # Generate the fixed number of elements for this component.
            if group_name == "DECK_SHELLS":  # Generate one four-node shell connectivity.
                start = ((element_id - 1) % (VALIDATOR.EXPECTED_POINT_COUNT - 3)) + 1  # Keep primary shell node labels inside 1..783.
                connectivity = [start, start + 1, start + 2, start + 3]  # Preserve deterministic quad ordering.
            elif group_name in GROUP_ORDER:  # Generate one nonzero primary two-node line connectivity.
                start = ((element_id - 1) % (VALIDATOR.EXPECTED_POINT_COUNT - 1)) + 1  # Keep primary line node labels inside 1..783.
                connectivity = [start, start + 1]  # Preserve deterministic primary line ordering.
            elif group_name == "WIND_ATTACH_LINKS":  # Connect four primary attachment nodes to four wind-only interface nodes.
                wind_index = _group_index * 2  # Allocate one even-indexed wind interface node per attachment link.
                connectivity = [1 + _group_index, 784 + wind_index]  # Preserve the baseline-derived primary-to-wind partition.
            else:  # Generate four two-node wind cables entirely inside the wind-only point set.
                wind_index = _group_index * 2  # Allocate one disjoint wind-only node pair per cable.
                connectivity = [784 + wind_index, 785 + wind_index]  # Cover wind-only nodes 784..791 exactly.
            groups[group_name].append((element_id, connectivity))  # Preserve the fixture cell for VTK construction.
            lines.append(f"{element_id}, " + ", ".join(str(node_id) for node_id in connectivity))  # Serialize the exact source connectivity.
            element_id += 1  # Advance to the next globally unique source element id.
    path.write_text("\n".join(lines) + "\n", encoding="ascii")  # Persist the complete frozen-contract fixture deck.
    return nodes, groups  # Return fixture topology for independent DAT and VTK generation.


def suspension_ids(groups: dict[str, list[tuple[int, list[int]]]]) -> set[int]:  # Recover exactly the fixture main-cable and hanger element ids.
    return {element_id for group_name in ("MAIN_CABLES", "HANGERS") for element_id, _connectivity in groups[group_name]}  # Return the complete target-stress id set.


def build_equilibrium(path: Path, baseline_sha256: str, groups: dict[str, list[tuple[int, list[int]]]]) -> dict[int, float]:  # Generate a complete PASS P2 fixture state.
    targets = {element_id: 10.0 for element_id in sorted(suspension_ids(groups))}  # Assign one finite positive target stress to every suspension element.
    state = {  # Assemble only fields required by the strict transfer contract.
        "schema": "zhaqing-equilibrium-state-v3",  # Require the complete full-system P1/P2 state identifier accepted by the canonical workflow.
        "status": "PASS",  # Make the generated P1/P2 fixture admissible to VTK validation.
        "sourceBaselineSha256": baseline_sha256,  # Bind state coordinates and stresses to the exact fixture deck.
        "nodeCoordinatesMm": {},  # Use the frozen baseline coordinates without overrides.
        "targetAxialStressMPa": {str(element_id): value for element_id, value in sorted(targets.items())},  # Publish every suspension target by source element label.
    }  # Finish the strict equilibrium-state fixture.
    write_json(path, state)  # Persist the finite unambiguous state receipt.
    return targets  # Return the same targets for independent VTK construction.


def build_dat(path: Path) -> None:  # Generate complete final NALL displacement and E_STRUCTURAL stress frames.
    lines = [" displacements (vx,vy,vz) for set NALL and time  0.1000000E+01", ""]  # Start the complete final nodal frame.
    for node_id in range(1, VALIDATOR.EXPECTED_POINT_COUNT + 1):  # Emit one raw result for every source node.
        lines.append(f"{node_id} 0.000000E+00 0.000000E+00 0.000000E+00")  # Keep the fixture response at the reference coordinates.
    lines.extend(("", "end of displacement frame"))  # Mirror CalculiX blank separation and terminate the nodal frame explicitly.
    lines.extend([" stresses (elem, integ.pnt.,sxx,syy,szz,sxy,sxz,syz) for set E_STRUCTURAL and time  0.1000000E+01", ""])  # Start the complete final stress frame.
    for element_id in range(1, VALIDATOR.EXPECTED_CELL_COUNT + 1):  # Emit raw P3 stress evidence for every structural element.
        for integration_point in range(1, 9):  # Emit all eight required integration-point records.
            lines.append(f"{element_id} {integration_point} 0 0 0 0 0 0")  # Keep the raw P3 perturbation tensor exactly zero without omitting evidence.
    lines.extend(("", " strains (elem, integ.pnt.) for set E_STRUCTURAL and time  0.1000000E+01"))  # Mirror CalculiX blank separation and terminate the stress frame explicitly.
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")  # Persist the complete strict raw-result fixture.


def build_wind_exclusion(path: Path, groups: dict[str, list[tuple[int, list[int]]]]) -> None:  # Publish exact baseline-derived G3/G5 wind exclusion evidence.
    excluded_groups = {group_name: [element_id for element_id, _connectivity in groups[group_name]] for group_name in VALIDATOR.EXCLUDED_WIND_GROUP_ORDER}  # Preserve exact source order inside both wind groups.
    excluded_element_ids = sorted(element_id for values in excluded_groups.values() for element_id in values)  # Flatten all eight unique excluded source element ids.
    receipt = {"schema": "zhaqing-wind-exclusion-v1", "status": "BLOCKED_G3_G5", "excludedGroups": excluded_groups, "excludedElementIds": excluded_element_ids, "windOnlyNodeIds": list(range(784, 792)), "blockerIssueIds": sorted(VALIDATOR.EXPECTED_WIND_BLOCKER_ISSUE_IDS)}  # Assemble the agreed explicit exclusion contract.
    write_json(path, receipt)  # Persist strict finite and duplicate-free exclusion evidence.


def build_cells(groups: dict[str, list[tuple[int, list[int]]]]) -> list[tuple[int, list[int], str]]:  # Flatten fixture elements into exact VTK component order.
    return [(element_id, connectivity, group_name) for group_name in GROUP_ORDER for element_id, connectivity in groups[group_name]]  # Preserve source order inside each component.


def build_vtk(path: Path, nodes: dict[int, tuple[float, float, float]], groups: dict[str, list[tuple[int, list[int]]]], targets: dict[int, float]) -> None:  # Generate one complete canonical VTK fixture independently.
    node_ids = list(range(1, VALIDATOR.EXPECTED_POINT_COUNT + 1))  # Freeze exactly the 783 primary source points and exclude wind-only nodes.
    point_index = {node_id: index for index, node_id in enumerate(node_ids)}  # Map source node labels to zero-based VTK indices.
    cells = build_cells(groups)  # Recover exact component and source cell order.
    lines = [  # Start the four-line canonical legacy VTK header.
        "# vtk DataFile Version 3.0",  # Declare the exact legacy format version.
        "Zhaqing suspension bridge stress-coordinated P4 result",  # Preserve the exact canonical dataset title.
        "ASCII",  # Require portable text serialization.
        "DATASET UNSTRUCTURED_GRID",  # Declare the finite-element grid dataset.
        f"POINTS {VALIDATOR.EXPECTED_POINT_COUNT} double",  # Declare complete point coverage and precision.
    ]  # Finish the header plus POINTS declaration.
    for node_id in node_ids:  # Serialize every undeformed fixture point in source order.
        lines.append(f"{node_id} 0 0")  # Match twelve-significant-digit output for integer x and zero y/z.
    lines.append(f"CELLS {VALIDATOR.EXPECTED_CELL_COUNT} {VALIDATOR.EXPECTED_CONNECTIVITY_INTEGER_COUNT}")  # Declare exact cell and connectivity counts.
    for _element_id, connectivity, _group_name in cells:  # Serialize every source connectivity in component order.
        lines.append(f"{len(connectivity)} " + " ".join(str(point_index[node_id]) for node_id in connectivity))  # Convert source labels to exact zero-based indices.
    lines.append(f"CELL_TYPES {VALIDATOR.EXPECTED_CELL_COUNT}")  # Declare one VTK type code per structural cell.
    for _element_id, _connectivity, group_name in cells:  # Serialize each fixed source-family mapping.
        lines.append("9" if group_name == "DECK_SHELLS" else "3")  # Map deck quads to VTK_QUAD and every line to VTK_LINE.
    lines.append(f"POINT_DATA {VALIDATOR.EXPECTED_POINT_COUNT}")  # Begin complete nodal response fields.
    lines.append("VECTORS displacement_mm double")  # Declare the exact physical displacement field.
    lines.extend("0 0 0" for _node_id in node_ids)  # Emit one explicit finite zero vector for every source node.
    lines.append(f"CELL_DATA {VALIDATOR.EXPECTED_CELL_COUNT}")  # Begin complete structural cell fields.
    lines.append("TENSORS stress_tensor_mpa double")  # Declare the exact coordinated stress tensor field.
    suspension = set(targets)  # Cache the elements receiving the independently composed P2 base tensor.
    for element_id, _connectivity, _group_name in cells:  # Emit one complete symmetric tensor per source cell.
        axial = 10.0 if element_id in suspension else 0.0  # Compose a pure x-axis P2 tensor only for suspension elements.
        lines.extend((f"{axial:.12g} 0 0", "0 0 0", "0 0 0"))  # Serialize the exact 3x3 symmetric tensor rows.
    component_codes = {name: index + 1 for index, name in enumerate(GROUP_ORDER)}  # Reconstruct stable component ids independently.
    fields: dict[str, list[float]] = {  # Allocate every required scalar field in canonical order.
        "von_mises_mpa": [10.0 if element_id in suspension else 0.0 for element_id, _connectivity, _group_name in cells],  # Recompute pure-uniaxial J2 values.
        "axial_stress_mpa": [10.0 if element_id in suspension else 0.0 for element_id, _connectivity, group_name in cells],  # Recompute line axial stress while shell values remain zero.
        "equilibrium_target_axial_stress_mpa": [targets.get(element_id, 0.0) for element_id, _connectivity, _group_name in cells],  # Preserve exact P2 targets.
        "stress_coordination_ratio": [1.0 if element_id in suspension else 0.0 for element_id, _connectivity, _group_name in cells],  # Recompute final-to-target ratios.
        "component_id": [float(component_codes[group_name]) for _element_id, _connectivity, group_name in cells],  # Preserve stable engineering component codes.
        "source_element_id": [float(element_id) for element_id, _connectivity, _group_name in cells],  # Preserve exact source element labels.
    }  # Finish all six independently generated scalar fields.
    for field_name in VALIDATOR.SCALAR_FIELD_ORDER:  # Serialize the exact required scalar order.
        lines.append(f"SCALARS {field_name} double 1")  # Declare one scalar value per structural cell.
        lines.append("LOOKUP_TABLE default")  # Use the canonical legacy lookup-table declaration.
        lines.extend(f"{value:.12g}" for value in fields[field_name])  # Emit every finite scalar in exact cell order.
    if len(lines) != VALIDATOR.EXPECTED_VTK_LINE_COUNT:  # Defend the generated golden fixture before testing the parser.
        raise RuntimeError(f"fixture VTK line count mismatch: {len(lines)}")  # Report an internal regression-fixture defect.
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")  # Persist the complete canonical VTK text.


def build_summary(path: Path, vtk_path: Path, baseline_sha256: str, equilibrium_sha256: str) -> None:  # Generate a producer receipt bound to exact fixture bytes.
    vtk_sha256 = sha256_path(vtk_path)  # Compute the delivered VTK digest independently.
    summary = {  # Assemble only producer fields consumed by the strict validator.
        "status": "PASS",  # Mark the numerical fixture as successful.
        "sourceBaselineSha256": baseline_sha256,  # Bind the producer summary to the exact fixture mother deck.
        "equilibriumStateSha256": equilibrium_sha256,  # Bind the producer summary to the exact fixture P2 state.
        "vtkSha256": vtk_sha256,  # Publish the top-level delivered VTK digest.
        "vtk": {  # Publish the nested visualization receipt returned by the writer.
            "pointCount": VALIDATOR.EXPECTED_POINT_COUNT,  # Report complete point coverage.
            "cellCount": VALIDATOR.EXPECTED_CELL_COUNT,  # Report complete structural-cell coverage.
            "maxVonMisesMPa": 10.0,  # Report the pure-uniaxial suspension maximum.
            "maxAbsAxialStressMPa": 10.0,  # Report the pure-uniaxial suspension axial maximum.
            "sha256": vtk_sha256,  # Publish the nested delivered VTK digest.
        },  # Finish the nested writer receipt.
    }  # Finish the producer summary fixture.
    write_json(path, summary)  # Persist strict finite JSON evidence.


def build_fixture(root: Path) -> dict[str, Path | str]:  # Build one complete independent fixed-contract evidence chain.
    baseline = root / "LC01_G_DEAD.inp"  # Resolve the fixture mother deck path.
    equilibrium = root / "equilibrium_state.json"  # Resolve the fixture P2 state path.
    dat = root / "ZQ_STRESS_COORDINATED.dat"  # Resolve the fixture raw final solver result path.
    vtk = root / "stress-coordinated.vtk"  # Resolve the fixture delivered visualization path.
    summary = root / "summary.json"  # Resolve the fixture producer receipt path.
    wind_exclusion = root / "wind-exclusion.json"  # Resolve the mandatory G3/G5 wind exclusion receipt path.
    nodes, groups = build_baseline(baseline)  # Generate exact source topology and geometry.
    baseline_sha256 = sha256_path(baseline)  # Freeze the generated baseline identity for this test fixture.
    targets = build_equilibrium(equilibrium, baseline_sha256, groups)  # Generate complete P2 coordinates and target stresses.
    build_dat(dat)  # Generate complete raw NALL and E_STRUCTURAL final frames.
    build_wind_exclusion(wind_exclusion, groups)  # Generate exact source-derived wind exclusion evidence.
    build_vtk(vtk, nodes, groups, targets)  # Generate all mandatory VTK sections and fields.
    build_summary(summary, vtk, baseline_sha256, sha256_path(equilibrium))  # Bind the producer receipt to exact fixture bytes.
    return {"baseline": baseline, "baselineSha256": baseline_sha256, "equilibrium": equilibrium, "dat": dat, "windExclusion": wind_exclusion, "vtk": vtk, "summary": summary}  # Return every explicit validation input.


def refresh_summary_vtk_digest(fixture: dict[str, Path | str]) -> None:  # Rebind both producer digest fields after an adversarial VTK mutation.
    summary_path = fixture["summary"]  # Recover the strict summary fixture path.
    vtk_path = fixture["vtk"]  # Recover the mutated VTK fixture path.
    if not isinstance(summary_path, Path) or not isinstance(vtk_path, Path):  # Defend fixture metadata types before mutation.
        raise RuntimeError("invalid fixture path metadata")  # Report an internal test defect rather than hiding it.
    summary = json.loads(summary_path.read_text(encoding="utf-8"))  # Load the known-valid fixture summary for controlled mutation.
    digest = sha256_path(vtk_path)  # Recompute the mutated delivered VTK digest.
    summary["vtkSha256"] = digest  # Keep the top-level producer digest internally consistent.
    summary["vtk"]["sha256"] = digest  # Keep the nested producer digest internally consistent.
    write_json(summary_path, summary)  # Persist the controlled adversarial receipt.


class StrictVtkValidatorRegressionTests(unittest.TestCase):  # Verify canonical success and representative fail-closed attacks.
    def setUp(self) -> None:  # Build a fresh complete evidence chain before every mutation.
        self.temporary = tempfile.TemporaryDirectory(prefix="zhaqing-vtk-validator-")  # Allocate an isolated disposable root.
        self.root = Path(self.temporary.name)  # Resolve the temporary root as a filesystem path.
        self.fixture = build_fixture(self.root)  # Generate complete valid baseline, state, DAT, VTK, and summary evidence.

    def tearDown(self) -> None:  # Remove the disposable regression evidence after each assertion.
        self.temporary.cleanup()  # Delete only the explicitly allocated temporary root.

    def validate(self) -> dict[str, Any]:  # Invoke the strict validator against the current fixture state.
        baseline = self.fixture["baseline"]  # Recover the fixture mother deck path.
        summary = self.fixture["summary"]  # Recover the fixture producer summary path.
        equilibrium = self.fixture["equilibrium"]  # Recover the fixture P2 state path.
        dat = self.fixture["dat"]  # Recover the fixture raw solver result path.
        vtk = self.fixture["vtk"]  # Recover the fixture delivered visualization path.
        wind_exclusion = self.fixture["windExclusion"]  # Recover the mandatory G3/G5 wind exclusion evidence path.
        baseline_sha256 = self.fixture["baselineSha256"]  # Recover the fixture-specific immutable baseline digest.
        self.assertTrue(all(isinstance(path, Path) for path in (baseline, summary, equilibrium, dat, vtk, wind_exclusion)))  # Defend typed fixture path metadata.
        self.assertIsInstance(baseline_sha256, str)  # Defend the fixture baseline identity type.
        return VALIDATOR.validate_artifacts(vtk, summary, baseline, equilibrium, dat, wind_exclusion, baseline_sha256)  # Execute the complete strict primary-response evidence-chain validation.

    def test_complete_fixed_contract_passes(self) -> None:  # Accept one complete independently generated 783/1070 primary artifact.
        receipt = self.validate()  # Validate every source, raw-result, field, and digest invariant.
        self.assertEqual(receipt["status"], "PASS")  # Require the independent receipt to announce PASS.
        self.assertEqual(receipt["contract"]["vtkLineCount"], VALIDATOR.EXPECTED_VTK_LINE_COUNT)  # Require the exact complete serialization size.
        self.assertIn("current-minus-F3 increment", receipt["contract"]["stressSemantics"]["MAIN_CABLES"])  # Require the receipt to declare tangent-or-nonlinear suspension stress composition explicitly.
        self.assertIn("final total", receipt["contract"]["stressSemantics"]["retainedStructure"])  # Require the receipt to declare retained-structure stress semantics explicitly.
        self.assertEqual(receipt["contract"]["excludedWindOnlyNodeIds"], list(range(784, 792)))  # Require exact wind-only point exclusion.

    def test_truncated_header_only_vtk_fails_even_with_matching_summary_digest(self) -> None:  # Reject the former title-only adversarial artifact.
        vtk_path = self.fixture["vtk"]  # Recover the delivered VTK fixture path.
        self.assertIsInstance(vtk_path, Path)  # Defend the fixture path type before mutation.
        original_lines = vtk_path.read_text(encoding="utf-8").splitlines()  # Read the valid canonical artifact once.
        vtk_path.write_text("\n".join(original_lines[:5]) + "\n", encoding="utf-8")  # Retain only headers and the POINTS declaration.
        refresh_summary_vtk_digest(self.fixture)  # Prevent a digest mismatch from masking truncation validation.
        with self.assertRaises(VALIDATOR.ValidationError):  # Require a fail-closed structural rejection.
            self.validate()  # Attempt to validate the truncated artifact.

    def test_non_finite_point_fails_even_with_matching_summary_digest(self) -> None:  # Reject NaN coordinates before any physical arithmetic.
        vtk_path = self.fixture["vtk"]  # Recover the delivered VTK fixture path.
        self.assertIsInstance(vtk_path, Path)  # Defend the fixture path type before mutation.
        lines = vtk_path.read_text(encoding="utf-8").splitlines()  # Read the complete valid artifact.
        lines[5] = "nan 0 0"  # Replace the first point with a non-finite numeric spelling.
        vtk_path.write_text("\n".join(lines) + "\n", encoding="utf-8")  # Preserve every declared count and section boundary.
        refresh_summary_vtk_digest(self.fixture)  # Keep producer digests consistent with the malicious bytes.
        with self.assertRaises(VALIDATOR.ValidationError):  # Require explicit non-finite rejection.
            self.validate()  # Attempt to validate the NaN-bearing artifact.

    def test_out_of_range_connectivity_fails_even_with_matching_summary_digest(self) -> None:  # Reject a dangling VTK point index.
        vtk_path = self.fixture["vtk"]  # Recover the delivered VTK fixture path.
        self.assertIsInstance(vtk_path, Path)  # Defend the fixture path type before mutation.
        lines = vtk_path.read_text(encoding="utf-8").splitlines()  # Read the complete valid artifact.
        cells_header = lines.index(f"CELLS {VALIDATOR.EXPECTED_CELL_COUNT} {VALIDATOR.EXPECTED_CONNECTIVITY_INTEGER_COUNT}")  # Locate the exact CELLS boundary.
        lines[cells_header + 1] = f"4 {VALIDATOR.EXPECTED_POINT_COUNT} 1 2 3"  # Insert index 783 outside the valid 0..782 primary range.
        vtk_path.write_text("\n".join(lines) + "\n", encoding="utf-8")  # Preserve declared sizes and every later field.
        refresh_summary_vtk_digest(self.fixture)  # Keep both producer digests synchronized with malicious bytes.
        with self.assertRaises(VALIDATOR.ValidationError):  # Require topology rejection before field acceptance.
            self.validate()  # Attempt to validate dangling connectivity.

    def test_missing_raw_element_stress_fails_before_p2_composition(self) -> None:  # Prevent P2 base stress from hiding absent P3 output.
        dat_path = self.fixture["dat"]  # Recover the raw final solver result path.
        self.assertIsInstance(dat_path, Path)  # Defend the fixture path type before mutation.
        lines = dat_path.read_text(encoding="utf-8").splitlines()  # Read the complete valid DAT result.
        retained = [line for line in lines if not (len(line.split()) >= 8 and line.split()[0] == str(VALIDATOR.EXPECTED_CELL_COUNT))]  # Remove all eight records for the final primary source element 1070.
        dat_path.write_text("\n".join(retained) + "\n", encoding="utf-8")  # Preserve an explicitly terminated but incomplete stress frame.
        with self.assertRaises(VALIDATOR.ValidationError):  # Require exact raw element-id coverage.
            self.validate()  # Attempt to compose and validate fields from incomplete P3 evidence.

    def test_nested_and_top_level_vtk_digest_divergence_fails(self) -> None:  # Require both summary digest locations to bind the same bytes.
        summary_path = self.fixture["summary"]  # Recover the producer summary path.
        self.assertIsInstance(summary_path, Path)  # Defend the fixture path type before mutation.
        summary = json.loads(summary_path.read_text(encoding="utf-8"))  # Load the known-valid fixture receipt.
        summary["vtkSha256"] = "0" * 64  # Diverge only the top-level digest while preserving nested truth.
        write_json(summary_path, summary)  # Persist the internally inconsistent producer receipt.
        with self.assertRaises(VALIDATOR.ValidationError):  # Require cross-digest rejection.
            self.validate()  # Attempt to validate a receipt with split artifact identity.

    def test_wrong_wind_blocker_set_fails(self) -> None:  # Require exact unresolved G3/G5 issues before excluding wind from primary response.
        exclusion_path = self.fixture["windExclusion"]  # Recover the mandatory wind-exclusion evidence path.
        self.assertIsInstance(exclusion_path, Path)  # Defend the fixture path type before mutation.
        exclusion = json.loads(exclusion_path.read_text(encoding="utf-8"))  # Load the known-valid exclusion receipt.
        exclusion["blockerIssueIds"] = ["U-WIND-001"]  # Omit both source reconciliation conflicts maliciously.
        write_json(exclusion_path, exclusion)  # Persist the incomplete blocker evidence.
        with self.assertRaises(VALIDATOR.ValidationError):  # Require exact blocker-set rejection.
            self.validate()  # Attempt primary validation without the agreed G3/G5 issue set.

    def test_wind_element_id_omission_fails(self) -> None:  # Require all eight baseline-derived wind elements in exclusion evidence.
        exclusion_path = self.fixture["windExclusion"]  # Recover the mandatory wind-exclusion evidence path.
        self.assertIsInstance(exclusion_path, Path)  # Defend the fixture path type before mutation.
        exclusion = json.loads(exclusion_path.read_text(encoding="utf-8"))  # Load the known-valid exclusion receipt.
        exclusion["excludedElementIds"] = exclusion["excludedElementIds"][:-1]  # Omit one source wind-cable element while preserving unique ids.
        write_json(exclusion_path, exclusion)  # Persist the incomplete element exclusion evidence.
        with self.assertRaises(VALIDATOR.ValidationError):  # Require exact eight-element coverage rejection.
            self.validate()  # Attempt primary validation with incomplete wind exclusion.

    def test_every_new_python_line_has_a_comment_marker(self) -> None:  # Lock the task's per-line audit-comment requirement for both new files.
        for path in (VALIDATOR_PATH, Path(__file__)):  # Inspect the implementation and this regression suite.
            for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):  # Visit every physical source line exactly once.
                if line.strip():  # Ignore intentionally empty readability separators.
                    self.assertIn("#", line, f"missing comment marker at {path}:{line_number}")  # Require an inline or standalone comment marker on every nonempty Python line.


if __name__ == "__main__":  # Execute the standard-library regression suite only when invoked explicitly.
    unittest.main()  # Propagate test failures through the native process exit code.
