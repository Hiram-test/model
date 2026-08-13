#!/usr/bin/env python3
"""Tool-call and completion-claim policy decisions."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Mapping

from bridge_fem_base import (
    CLAIM_GATE,
    CLAIM_NODE,
    command_markers,
    contains_marker,
    matches_any,
    normalized_tool_text,
    policy_patterns,
    protected_contract_touched,
    tool_is_mutating,
    verify_contract_snapshot,
)
from bridge_fem_receipts import (
    detailed_result_access,
    independent_plan_frozen,
    validate_gate_chain,
    validate_gate_receipt,
    validate_solver_barrier,
)


def pre_tool_decision(
    root: Path,
    policy: Mapping[str, Any],
    state: Mapping[str, Any] | None,
    payload: Mapping[str, Any],
) -> str | None:
    tool_name = str(payload.get("tool_name", ""))
    text = normalized_tool_text(payload)
    mutating = tool_is_mutating(tool_name, text)
    is_solver = matches_any(policy_patterns(policy, "solverCommands"), text)
    is_deck_write = mutating and matches_any(policy_patterns(policy, "solverDeckWrites"), text)
    is_release_write = mutating and matches_any(policy_patterns(policy, "releaseWrites"), text)
    is_gate_write = mutating and matches_any(policy_patterns(policy, "gateStateWrites"), text)
    is_run_write = mutating and matches_any(policy_patterns(policy, "runStateWrites"), text)

    if state is None:
        if is_solver or is_deck_write:
            return "没有 active Bridge FEM run，禁止生成 solver deck 或启动求解。"
        if is_gate_write:
            return "没有 active Bridge FEM run，禁止写 Gate receipt/ledger。"
        if is_release_write:
            return "没有 active Bridge FEM run，禁止生成 release。"
        if is_run_write and not contains_marker(text, command_markers(policy, "runControllerMarkers")):
            return "run 状态只能由 bridge_fem_run.py init/enter/close 管理。"
        return None

    if state.get("compromised"):
        return f"当前 run 已标记 COMPROMISED：{state.get('compromiseReason', '契约完整性失败')}"

    if mutating:
        touched = protected_contract_touched(policy, text)
        if touched:
            return "active run 期间禁止修改 Skill/workflow/schema/hook policy：" + ", ".join(touched)

    if is_run_write and not contains_marker(text, command_markers(policy, "runControllerMarkers")):
        return "current.json 和 run 状态只能由 bridge_fem_run.py 管理。"

    if is_gate_write and not contains_marker(text, command_markers(policy, "gateEvaluatorMarkers")):
        return "专业节点不得直接写 Gate 状态；请调用独立 bridge_fem_gate_validator。"

    if is_solver or is_deck_write:
        errors = validate_solver_barrier(root, policy, state)
        if errors:
            return "N14 solver barrier 未通过：" + "；".join(errors[:12])

    if state.get("activeNode") in {"N16", "N18"} and detailed_result_access(text, policy):
        return f"{state.get('activeNode')} 只能消费经验证/复核工件，禁止直接读取 raw solver result。"

    if state.get("activeNode") == "N17" and detailed_result_access(text, policy) and not independent_plan_frozen(root, state):
        return "N17 在读取详细 solver 结果前必须冻结 independent_check_plan.json 并登记哈希。"

    if is_release_write:
        if state.get("activeNode") != "N18":
            return f"release 只能在 N18 生成，当前节点为 {state.get('activeNode')}。"
        required = list(policy.get("formalPolicy", {}).get("releaseEntryGates", []))
        strict = set(required) if state.get("mode") == "FORMAL" else set()
        errors = validate_gate_chain(root, policy, state, required, strict_gates=strict)
        if errors:
            return "N18 release barrier 未通过：" + "；".join(errors[:12])
        if not contains_marker(text, command_markers(policy, "releaseBuilderMarkers")):
            return "release 工件只能由确定性 bridge_fem_release builder 生成。"

    return None


def receipt_requirements_from_claim(
    message: str, policy: Mapping[str, Any]
) -> tuple[set[str], set[str]]:
    """Return (structural_receipts, strict_pass_receipts) implied by a claim."""
    structural: set[str] = set()
    strict: set[str] = set()
    for match in CLAIM_NODE.finditer(message):
        node = match.group(1).upper()
        verb = match.group(2).upper()
        cfg = policy.get("nodes", {}).get(node)
        if isinstance(cfg, Mapping):
            gate = str(cfg.get("gate"))
            structural.add(gate)
            if verb in {"PASS", "通过"}:
                strict.add(gate)
    for match in CLAIM_GATE.finditer(message):
        gate = match.group(1).upper()
        structural.add(gate)
        strict.add(gate)
    lowered = message.lower()
    if re.search(r"求解|solver", message, re.IGNORECASE) and re.search(r"完成|成功|通过|pass", message, re.IGNORECASE):
        structural.add("G12")
        strict.add("G12")
    if re.search(r"解验证|solution verification|verified result", message, re.IGNORECASE):
        structural.add("G13")
        strict.add("G13")
    if re.search(r"规范复核|静力复核|code review", message, re.IGNORECASE):
        structural.add("G14")
        strict.add("G14")
    if re.search(r"独立复核|可信度|sensitivity", message, re.IGNORECASE):
        structural.add("G15")
        strict.add("G15")
    if re.search(r"发布|release", message, re.IGNORECASE):
        structural.add("G16")
        strict.add("G16")
    if "19/19" in lowered or "十九个skill" in lowered.replace(" ", ""):
        structural.update(str(cfg.get("gate")) for cfg in policy.get("nodes", {}).values())
    structural.discard("None")
    strict.discard("None")
    return structural, strict


def completion_claim_errors(
    root: Path,
    policy: Mapping[str, Any],
    state: Mapping[str, Any] | None,
    message: str,
) -> list[str]:
    if not matches_any(policy_patterns(policy, "completionClaims"), message):
        return []
    if state is None:
        return ["答复包含 Bridge FEM 完成/通过声明，但仓库没有 active run。"]
    structural, strict = receipt_requirements_from_claim(message, policy)
    if not structural:
        active = str(state.get("activeNode", ""))
        cfg = policy.get("nodes", {}).get(active)
        if isinstance(cfg, Mapping):
            structural.add(str(cfg.get("gate")))
    errors: list[str] = []
    for gate in sorted(structural):
        _, gate_errors = validate_gate_receipt(
            root,
            policy,
            state,
            gate,
            require_strict_pass=gate in strict,
            require_usable=gate in strict,
        )
        errors.extend(gate_errors)
    errors.extend(verify_contract_snapshot(root, state))
    return errors
