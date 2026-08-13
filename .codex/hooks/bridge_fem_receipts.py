#!/usr/bin/env python3
"""Gate receipt validation and transition barriers."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from bridge_fem_base import (
    HEX64,
    PolicyError,
    _receipt_check_ids,
    artifact_root,
    load_json,
    matches_any,
    policy_patterns,
    receipt_path,
    resolve_inside,
    sha256_file,
)


def validate_gate_receipt(
    root: Path,
    policy: Mapping[str, Any],
    state: Mapping[str, Any],
    gate_id: str,
    *,
    require_strict_pass: bool = False,
    require_usable: bool = False,
) -> tuple[dict[str, Any] | None, list[str]]:
    errors: list[str] = []
    nodes = policy.get("nodes", {})
    node_id = next((nid for nid, cfg in nodes.items() if cfg.get("gate") == gate_id), None)
    if node_id is None:
        return None, [f"policy 未登记 Gate：{gate_id}"]
    cfg = nodes[node_id]
    path = receipt_path(root, state, gate_id)
    if not path.is_file():
        return None, [f"缺少 Gate receipt：{path.relative_to(root)}"]
    try:
        receipt = load_json(path)
    except Exception as exc:  # noqa: BLE001 - hook must report malformed files
        return None, [f"Gate receipt 无法解析：{path.relative_to(root)}：{exc}"]
    if not isinstance(receipt, dict):
        return None, [f"Gate receipt 必须为 object：{path.relative_to(root)}"]

    expected_pairs = {
        "projectId": state.get("projectId"),
        "runId": state.get("runId"),
        "nodeId": node_id,
        "gateId": gate_id,
    }
    for key, expected in expected_pairs.items():
        if receipt.get(key) != expected:
            errors.append(f"{gate_id} receipt {key}={receipt.get(key)!r}，期望 {expected!r}")

    skill = receipt.get("skill")
    if not isinstance(skill, Mapping):
        errors.append(f"{gate_id} 缺少 skill 证据")
    else:
        if skill.get("name") != cfg.get("skill"):
            errors.append(f"{gate_id} skill.name 与节点配置不一致")
        if not HEX64.fullmatch(str(skill.get("sha256", ""))):
            errors.append(f"{gate_id} skill.sha256 无效")
        if not str(skill.get("version", "")).strip():
            errors.append(f"{gate_id} skill.version 缺失")

    count = int(cfg.get("criteriaCount", 0))
    summary = receipt.get("criterionSummary")
    if not isinstance(summary, Mapping):
        errors.append(f"{gate_id} 缺少 criterionSummary")
    else:
        expected_summary_fields = {"required", "executed", "passed", "failed", "unimplemented", "notApplicable"}
        missing = expected_summary_fields - set(summary)
        if missing:
            errors.append(f"{gate_id} criterionSummary 缺少 {sorted(missing)}")
        if summary.get("required") != count:
            errors.append(f"{gate_id} required={summary.get('required')}，期望 {count}")
        if summary.get("executed") != count:
            errors.append(f"{gate_id} executed={summary.get('executed')}，必须逐条执行 {count} 项")

    checks = receipt.get("checks")
    expected_ids = _receipt_check_ids(gate_id, count)
    if not isinstance(checks, list):
        errors.append(f"{gate_id} checks 必须为数组")
    else:
        actual_ids = {str(item.get("criterionId")) for item in checks if isinstance(item, Mapping)}
        if actual_ids != expected_ids:
            errors.append(
                f"{gate_id} criteria 覆盖不完整；missing={sorted(expected_ids - actual_ids)}，"
                f"extra={sorted(actual_ids - expected_ids)}"
            )
        for item in checks:
            if not isinstance(item, Mapping):
                errors.append(f"{gate_id} 存在非 object check")
                continue
            criterion = str(item.get("criterionId", "UNKNOWN"))
            if item.get("mandatory") is not True:
                errors.append(f"{criterion} 未标记 mandatory=true")
            if not str(item.get("checkerId", "")).strip() or not str(item.get("checkerVersion", "")).strip():
                errors.append(f"{criterion} 缺少 checkerId/checkerVersion")
            evidence = item.get("evidenceRefs")
            if not isinstance(evidence, list) or not evidence:
                errors.append(f"{criterion} 缺少 evidenceRefs")

    blockers = receipt.get("blockers")
    blocker_keys = ["criticalConflicts", "criticalOrphans", "unapprovedHighSensitivityAssumptions", "blockingIssues"]
    blocker_values: dict[str, list[Any]] = {}
    if not isinstance(blockers, Mapping):
        errors.append(f"{gate_id} 缺少 blockers")
    else:
        for key in blocker_keys:
            value = blockers.get(key)
            if not isinstance(value, list):
                errors.append(f"{gate_id} blockers.{key} 必须为数组")
            else:
                blocker_values[key] = value

    validator = receipt.get("validator")
    if not isinstance(validator, Mapping):
        errors.append(f"{gate_id} 缺少独立 validator 证据")
    else:
        if validator.get("deterministic") is not True:
            errors.append(f"{gate_id} validator.deterministic 必须为 true")
        if not str(validator.get("id", "")).strip() or not str(validator.get("version", "")).strip():
            errors.append(f"{gate_id} validator id/version 缺失")
        if not HEX64.fullmatch(str(validator.get("sha256", ""))):
            errors.append(f"{gate_id} validator.sha256 无效")

    status = receipt.get("status")
    allowed_status = {"PASS", "PASS_WITH_BOUNDS", "BLOCKED", "NOT_APPLICABLE"}
    if status not in allowed_status:
        errors.append(f"{gate_id} status 非法：{status}")
    conditional_na = gate_id in set(policy.get("formalPolicy", {}).get("conditionalNotApplicableGates", []))
    has_blockers = any(blocker_values.get(key) for key in blocker_keys)
    if require_strict_pass and status != "PASS":
        if not (conditional_na and status == "NOT_APPLICABLE"):
            errors.append(f"{gate_id} 正式通行要求严格 PASS，当前为 {status}")
    if require_usable and status not in {"PASS", "PASS_WITH_BOUNDS", "NOT_APPLICABLE"}:
        errors.append(f"{gate_id} 当前状态 {status} 不允许下游消费")
    if require_usable and has_blockers:
        errors.append(f"{gate_id} 存在阻断项，不允许下游消费")

    unimplemented_count = summary.get("unimplemented", 0) if isinstance(summary, Mapping) else 0
    check_has_unimplemented = bool(
        isinstance(checks, list)
        and any(isinstance(item, Mapping) and item.get("status") == "NOT_IMPLEMENTED" for item in checks)
    )
    if status in {"PASS", "PASS_WITH_BOUNDS", "NOT_APPLICABLE"} and (
        unimplemented_count or check_has_unimplemented
    ):
        errors.append(f"{gate_id} 状态 {status} 不能包含未实现强制条件")
    if require_usable and (unimplemented_count or check_has_unimplemented):
        errors.append(f"{gate_id} 存在未实现强制条件，不允许下游消费")

    if status == "PASS":
        if isinstance(summary, Mapping) and (summary.get("failed") != 0 or summary.get("passed") != count):
            errors.append(f"{gate_id} PASS 与 criterionSummary 不一致")
        if has_blockers:
            errors.append(f"{gate_id} PASS 不能包含 blocker")
    elif status == "PASS_WITH_BOUNDS":
        bounds = receipt.get("bounds")
        if not isinstance(bounds, list) or not bounds:
            errors.append(f"{gate_id} PASS_WITH_BOUNDS 缺少 bounds")
        if has_blockers:
            errors.append(f"{gate_id} PASS_WITH_BOUNDS 不能包含 blocker")
    elif status == "BLOCKED":
        failed = summary.get("failed", 0) if isinstance(summary, Mapping) else 0
        if not has_blockers and failed == 0 and not unimplemented_count and not check_has_unimplemented:
            errors.append(f"{gate_id} BLOCKED 缺少失败条件、未实现条件或 blocker")
    elif status == "NOT_APPLICABLE":
        if gate_id not in set(policy.get("formalPolicy", {}).get("conditionalNotApplicableGates", [])):
            errors.append(f"{gate_id} 不允许 NOT_APPLICABLE")
        if not str(receipt.get("notApplicableReason", "")).strip():
            errors.append(f"{gate_id} NOT_APPLICABLE 缺少理由")
        refs = receipt.get("conditionEvidenceRefs")
        if not isinstance(refs, list) or not refs:
            errors.append(f"{gate_id} NOT_APPLICABLE 缺少 conditionEvidenceRefs")

    approvals = receipt.get("approvals")
    if not isinstance(approvals, list):
        errors.append(f"{gate_id} approvals 必须为数组")
        approvals = []
    approved_roles = {
        str(item.get("role"))
        for item in approvals
        if isinstance(item, Mapping)
        and item.get("status") == "APPROVED"
        and HEX64.fullmatch(str(item.get("artifactHash", "")))
    }
    missing_roles = set(cfg.get("requiredApprovals", [])) - approved_roles
    if missing_roles:
        errors.append(f"{gate_id} 缺少审批角色：{sorted(missing_roles)}")

    artifacts = receipt.get("artifactHashes")
    if status != "NOT_APPLICABLE":
        if not isinstance(artifacts, Mapping):
            errors.append(f"{gate_id} artifactHashes 必须为 object")
        else:
            required_artifacts = set(cfg.get("requiredArtifacts", []))
            missing_artifacts = required_artifacts - set(artifacts)
            if missing_artifacts:
                errors.append(f"{gate_id} 缺少规定工件哈希：{sorted(missing_artifacts)}")
            for name in required_artifacts & set(artifacts):
                entry = artifacts.get(name)
                if not isinstance(entry, Mapping):
                    errors.append(f"{gate_id} artifactHashes.{name} 格式错误")
                    continue
                relative = entry.get("path")
                expected_hash = str(entry.get("sha256", ""))
                if not isinstance(relative, str) or not HEX64.fullmatch(expected_hash):
                    errors.append(f"{gate_id} {name} path/sha256 无效")
                    continue
                try:
                    artifact_path = resolve_inside(root, relative)
                except PolicyError as exc:
                    errors.append(str(exc))
                    continue
                if not artifact_path.is_file():
                    errors.append(f"{gate_id} 工件不存在：{relative}")
                elif sha256_file(artifact_path) != expected_hash.lower():
                    errors.append(f"{gate_id} 工件哈希不一致：{relative}")

    return receipt, errors


def validate_gate_chain(
    root: Path,
    policy: Mapping[str, Any],
    state: Mapping[str, Any],
    gate_ids: Sequence[str],
    *,
    strict_gates: Iterable[str] = (),
    require_usable: bool = True,
) -> list[str]:
    errors: list[str] = []
    strict = set(strict_gates)
    for gate_id in gate_ids:
        _, gate_errors = validate_gate_receipt(
            root,
            policy,
            state,
            gate_id,
            require_strict_pass=gate_id in strict,
            require_usable=require_usable,
        )
        errors.extend(gate_errors)
    return errors


def validate_node_completion(
    root: Path,
    policy: Mapping[str, Any],
    state: Mapping[str, Any],
    node_id: str,
) -> list[str]:
    cfg = policy.get("nodes", {}).get(node_id)
    if not isinstance(cfg, Mapping):
        return [f"未知节点：{node_id}"]
    gate_id = str(cfg.get("gate"))
    _, errors = validate_gate_receipt(root, policy, state, gate_id)
    return errors


def validate_solver_barrier(root: Path, policy: Mapping[str, Any], state: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if state.get("activeNode") != policy.get("formalPolicy", {}).get("solverEntryNode"):
        errors.append(f"solver 只能在 N14 执行，当前节点为 {state.get('activeNode')}")
    gates = list(policy.get("formalPolicy", {}).get("solverPrerequisiteGates", []))
    strict = set(policy.get("formalPolicy", {}).get("strictSolverGates", [])) if state.get("mode") == "FORMAL" else set()
    errors.extend(validate_gate_chain(root, policy, state, gates, strict_gates=strict))
    if state.get("mode") == "RESEARCH" and not state.get("allowResearchSolve", False):
        errors.append("RESEARCH run 未显式设置 allowResearchSolve=true")
    return errors


def detailed_result_access(text: str, policy: Mapping[str, Any]) -> bool:
    return matches_any(policy_patterns(policy, "rawResultPaths"), text)


def independent_plan_frozen(root: Path, state: Mapping[str, Any]) -> bool:
    plan = artifact_root(root, state) / "N17" / "independent_check_plan.json"
    freeze = state.get("independentCheckPlanSha256")
    return plan.is_file() and isinstance(freeze, str) and HEX64.fullmatch(freeze) and sha256_file(plan) == freeze.lower()
