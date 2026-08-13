from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

HOOK_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HOOK_ROOT))

import bridge_fem_base as base
import bridge_fem_policy as policy_module
import bridge_fem_hooks as dispatcher
import bridge_fem_receipts as receipts


class BridgeFemHookTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / ".codex/hooks").mkdir(parents=True)
        self.policy = {
            "stateFile": ".bridge-fem/current.json",
            "auditRoot": ".bridge-fem/audit",
            "formalPolicy": {
                "solverEntryNode": "N14",
                "strictSolverGates": ["G3"],
                "solverPrerequisiteGates": ["G3"],
                "conditionalNotApplicableGates": ["G8B"],
                "releaseEntryGates": ["G3"],
            },
            "approvedCommands": {
                "runControllerMarkers": ["bridge_fem_run.py init", "bridge_fem_run.py enter"],
                "gateEvaluatorMarkers": ["bridge_fem_gate_validator.py"],
                "releaseBuilderMarkers": ["bridge_fem_release.py"],
            },
            "patterns": {
                "solverCommands": [r"\bmapdl\b"],
                "solverDeckWrites": [r"solver[_-]?deck"],
                "rawResultPaths": [r"\.rst(?:\s|$|\")"],
                "releaseWrites": ["release_manifest"],
                "gateStateWrites": ["gate-receipts", "gate_ledger"],
                "runStateWrites": [r"\.bridge-fem[/\\]current\.json"],
                "completionClaims": [r"G3[^\n]{0,20}PASS", r"N04[^\n]{0,20}完成"],
            },
            "protectedContractFiles": ["contract.txt"],
            "nodes": {
                "N04": {
                    "skill": "registration",
                    "gate": "G3",
                    "criteriaCount": 2,
                    "requiredUpstreamGates": [],
                    "requiredApprovals": [],
                    "requiredArtifacts": ["evidence_graph.json", "overlay.json"],
                },
                "N14": {
                    "skill": "solver",
                    "gate": "G12",
                    "criteriaCount": 1,
                    "requiredUpstreamGates": ["G3"],
                    "requiredApprovals": [],
                    "requiredArtifacts": ["solver_run_record.json"],
                },
                "N17": {
                    "skill": "independent",
                    "gate": "G15",
                    "criteriaCount": 1,
                    "requiredUpstreamGates": [],
                    "requiredApprovals": [],
                    "requiredArtifacts": ["independent_check_plan.json"],
                },
            },
        }
        (self.root / ".codex/hooks/node_hook_policy.json").write_text(
            json.dumps(self.policy), encoding="utf-8"
        )
        (self.root / "contract.txt").write_text("contract-v1", encoding="utf-8")
        self.state = {
            "projectId": "P",
            "runId": "R",
            "mode": "FORMAL",
            "activeNode": "N04",
            "artifactRoot": ".bridge-fem/runs/R/artifacts",
            "gateReceiptRoot": ".bridge-fem/runs/R/gate-receipts",
            "contractSnapshot": {"contract.txt": base.sha256_file(self.root / "contract.txt")},
        }
        (self.root / ".bridge-fem/runs/R/artifacts/N04").mkdir(parents=True)
        (self.root / ".bridge-fem/runs/R/gate-receipts").mkdir(parents=True)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _write_artifact(self, name: str, content: str = "{}") -> dict[str, str]:
        path = self.root / ".bridge-fem/runs/R/artifacts/N04" / name
        path.write_text(content, encoding="utf-8")
        return {"path": path.relative_to(self.root).as_posix(), "sha256": base.sha256_file(path)}

    def _write_receipt(self, status: str = "PASS", unimplemented: int = 0) -> None:
        artifacts = {
            "evidence_graph.json": self._write_artifact("evidence_graph.json"),
            "overlay.json": self._write_artifact("overlay.json"),
        }
        checks = [
            {
                "criterionId": "G3.1",
                "mandatory": True,
                "status": "PASS",
                "checkerId": "c1",
                "checkerVersion": "1",
                "inputArtifactRefs": ["a"],
                "evidenceRefs": ["e1"],
            },
            {
                "criterionId": "G3.2",
                "mandatory": True,
                "status": "PASS" if unimplemented == 0 else "NOT_IMPLEMENTED",
                "checkerId": "c2",
                "checkerVersion": "1",
                "inputArtifactRefs": ["a"],
                "evidenceRefs": ["e2"],
            },
        ]
        receipt = {
            "schemaVersion": "1.0.0",
            "projectId": "P",
            "runId": "R",
            "nodeId": "N04",
            "gateId": "G3",
            "skill": {"name": "registration", "version": "1", "sha256": "a" * 64},
            "status": status,
            "criterionSummary": {
                "required": 2,
                "executed": 2,
                "passed": 2 - unimplemented,
                "failed": 0,
                "unimplemented": unimplemented,
                "notApplicable": 0,
            },
            "checks": checks,
            "blockers": {
                "criticalConflicts": [],
                "criticalOrphans": [],
                "unapprovedHighSensitivityAssumptions": [],
                "blockingIssues": [],
            },
            "bounds": [{"id": "b1"}] if status == "PASS_WITH_BOUNDS" else [],
            "validator": {"id": "v", "version": "1", "sha256": "b" * 64, "deterministic": True},
            "artifactHashes": artifacts,
            "approvals": [],
            "evaluatedAt": "2026-07-22T00:00:00Z",
        }
        path = self.root / ".bridge-fem/runs/R/gate-receipts/G3.json"
        path.write_text(json.dumps(receipt), encoding="utf-8")

    def test_post_tool_use_writes_audit_record(self) -> None:
        payload = {
            "hook_event_name": "PostToolUse",
            "cwd": str(self.root),
            "session_id": "S-1",
            "turn_id": "T-1",
            "tool_name": "Bash",
            "tool_use_id": "U-1",
            "tool_input": {"command": "git status"},
            "tool_response": {"ok": True},
        }
        result = dispatcher.handle_hook(payload)
        self.assertEqual(0, result)
        audit = self.root / ".bridge-fem/audit/S-1.jsonl"
        self.assertTrue(audit.is_file())
        record = json.loads(audit.read_text(encoding="utf-8").splitlines()[0])
        self.assertEqual("PostToolUse", record["event"])
        self.assertEqual("U-1", record["toolUseId"])

    def test_solver_without_active_run_is_blocked(self) -> None:
        payload = {"tool_name": "Bash", "tool_input": {"command": "mapdl -b -i model.dat"}}
        reason = policy_module.pre_tool_decision(self.root, self.policy, None, payload)
        self.assertIn("没有 active", reason or "")

    def test_complete_receipt_passes(self) -> None:
        self._write_receipt()
        _, errors = receipts.validate_gate_receipt(self.root, self.policy, self.state, "G3", require_strict_pass=True)
        self.assertEqual([], errors)

    def test_unimplemented_criterion_cannot_pass(self) -> None:
        self._write_receipt(unimplemented=1)
        _, errors = receipts.validate_gate_receipt(self.root, self.policy, self.state, "G3")
        self.assertTrue(any("不能包含未实现" in error for error in errors))

    def test_unimplemented_criterion_can_be_reported_as_blocked(self) -> None:
        self._write_receipt(status="PASS", unimplemented=1)
        path = self.root / ".bridge-fem/runs/R/gate-receipts/G3.json"
        receipt = json.loads(path.read_text(encoding="utf-8"))
        receipt["status"] = "BLOCKED"
        receipt["blockers"]["blockingIssues"] = ["VALIDATOR-NOT-IMPLEMENTED"]
        path.write_text(json.dumps(receipt), encoding="utf-8")
        _, errors = receipts.validate_gate_receipt(self.root, self.policy, self.state, "G3")
        self.assertEqual([], errors)

    def test_formal_solver_rejects_pass_with_bounds(self) -> None:
        self._write_receipt(status="PASS_WITH_BOUNDS")
        state = dict(self.state, activeNode="N14")
        errors = receipts.validate_solver_barrier(self.root, self.policy, state)
        self.assertTrue(any("严格 PASS" in error for error in errors))

    def test_contract_change_marks_error(self) -> None:
        (self.root / "contract.txt").write_text("changed", encoding="utf-8")
        errors = base.verify_contract_snapshot(self.root, self.state)
        self.assertTrue(any("哈希变化" in error for error in errors))

    def test_n17_raw_result_requires_frozen_plan(self) -> None:
        state = dict(self.state, activeNode="N17")
        payload = {"tool_name": "Bash", "tool_input": {"command": "python inspect.py model.rst"}}
        reason = policy_module.pre_tool_decision(self.root, self.policy, state, payload)
        self.assertIn("冻结 independent_check_plan", reason or "")

    def test_blocked_node_can_finish_with_complete_receipt(self) -> None:
        self._write_receipt(status="PASS")
        path = self.root / ".bridge-fem/runs/R/gate-receipts/G3.json"
        receipt = json.loads(path.read_text(encoding="utf-8"))
        receipt["status"] = "BLOCKED"
        receipt["criterionSummary"]["passed"] = 1
        receipt["criterionSummary"]["failed"] = 1
        receipt["checks"][1]["status"] = "FAIL"
        receipt["blockers"]["blockingIssues"] = ["ISSUE-1"]
        path.write_text(json.dumps(receipt), encoding="utf-8")
        errors = policy_module.completion_claim_errors(self.root, self.policy, self.state, "N04 已完成，G3=BLOCKED")
        self.assertEqual([], errors)

    def test_completion_claim_without_receipt_is_blocked(self) -> None:
        errors = policy_module.completion_claim_errors(self.root, self.policy, self.state, "N04 已完成，G3 PASS")
        self.assertTrue(errors)


if __name__ == "__main__":
    unittest.main()
