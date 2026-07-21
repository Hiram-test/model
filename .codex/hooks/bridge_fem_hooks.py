#!/usr/bin/env python3
"""Codex hook dispatcher for Bridge FEM N00-N18."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

from bridge_fem_base import (
    atomic_write_json,
    find_repo_root,
    json_dump,
    load_policy,
    load_state,
    resolve_inside,
    sha256_bytes,
    state_context,
    state_path,
    utc_now,
    verify_contract_snapshot,
)
from bridge_fem_policy import completion_claim_errors, pre_tool_decision


def emit(data: Mapping[str, Any] | None = None) -> None:
    if data is not None:
        sys.stdout.write(json.dumps(data, ensure_ascii=False) + "\n")


def deny_pre_tool(reason: str) -> None:
    emit(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": reason,
            }
        }
    )


def deny_permission(reason: str) -> None:
    emit(
        {
            "hookSpecificOutput": {
                "hookEventName": "PermissionRequest",
                "decision": {"behavior": "deny", "message": reason},
            }
        }
    )


def context_output(event: str, context: str) -> None:
    emit({"hookSpecificOutput": {"hookEventName": event, "additionalContext": context}})


def append_audit(root: Path, policy: Mapping[str, Any], payload: Mapping[str, Any], state: Mapping[str, Any] | None) -> None:
    audit_root = resolve_inside(root, policy.get("auditRoot", ".bridge-fem/audit"))
    audit_root.mkdir(parents=True, exist_ok=True)
    session = re.sub(r"[^A-Za-z0-9_.-]", "_", str(payload.get("session_id", "unknown")))[:120]
    record = {
        "at": utc_now(),
        "sessionId": payload.get("session_id"),
        "turnId": payload.get("turn_id"),
        "event": payload.get("hook_event_name"),
        "toolName": payload.get("tool_name"),
        "toolUseId": payload.get("tool_use_id"),
        "toolInput": payload.get("tool_input"),
        "toolResponseSha256": sha256_bytes(json_dump(payload.get("tool_response")).encode("utf-8")),
        "runId": state.get("runId") if state else None,
        "activeNode": state.get("activeNode") if state else None,
    }
    with (audit_root / f"{session}.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record, ensure_ascii=False) + "\n")


def mark_compromised(root: Path, policy: Mapping[str, Any], state: dict[str, Any], errors: Sequence[str]) -> None:
    state["compromised"] = True
    state["compromiseReason"] = "; ".join(errors[:20])
    state["compromisedAt"] = utc_now()
    atomic_write_json(state_path(root, policy), state)


def handle_hook(payload: Mapping[str, Any]) -> int:
    root = find_repo_root(payload.get("cwd"))
    try:
        policy = load_policy(root)
        state = load_state(root, policy)
    except Exception as exc:  # noqa: BLE001
        event = str(payload.get("hook_event_name", ""))
        reason = f"Bridge FEM Hook 初始化失败：{exc}"
        if event == "PreToolUse":
            deny_pre_tool(reason)
        elif event == "PermissionRequest":
            deny_permission(reason)
        elif event in {"Stop", "SubagentStop", "UserPromptSubmit"}:
            emit({"decision": "block", "reason": reason})
        else:
            emit({"systemMessage": reason})
        return 0

    event = str(payload.get("hook_event_name", ""))

    if event in {"SessionStart", "PostCompact", "SubagentStart", "UserPromptSubmit"}:
        context_output(event, state_context(policy, state))
        return 0

    if event == "PreCompact":
        if state is not None:
            audit_root = resolve_inside(root, policy.get("auditRoot", ".bridge-fem/audit"))
            audit_root.mkdir(parents=True, exist_ok=True)
            snapshot = {
                "at": utc_now(),
                "sessionId": payload.get("session_id"),
                "turnId": payload.get("turn_id"),
                "trigger": payload.get("trigger"),
                "state": state,
            }
            atomic_write_json(audit_root / f"compact-{payload.get('session_id', 'unknown')}.json", snapshot)
        emit({})
        return 0

    if event == "PreToolUse":
        reason = pre_tool_decision(root, policy, state, payload)
        if reason:
            deny_pre_tool(reason)
        return 0

    if event == "PermissionRequest":
        reason = pre_tool_decision(root, policy, state, payload)
        if reason:
            deny_permission(reason)
        return 0

    if event == "PostToolUse":
        append_audit(root, policy, payload, state)
        if state is not None:
            errors = verify_contract_snapshot(root, state)
            if errors:
                mutable_state = dict(state)
                mark_compromised(root, policy, mutable_state, errors)
                emit(
                    {
                        "decision": "block",
                        "reason": "active run 的受保护契约发生变化，run 已标记 COMPROMISED。",
                        "hookSpecificOutput": {
                            "hookEventName": "PostToolUse",
                            "additionalContext": "；".join(errors[:12]),
                        },
                    }
                )
        return 0

    if event in {"Stop", "SubagentStop"}:
        if payload.get("stop_hook_active"):
            emit({})
            return 0
        message = str(payload.get("last_assistant_message") or "")
        errors = completion_claim_errors(root, policy, state, message)
        if errors:
            emit(
                {
                    "decision": "block",
                    "reason": (
                        "撤回当前完成/通过表述，先补齐或重算以下证据：\n- "
                        + "\n- ".join(errors[:20])
                    ),
                }
            )
        else:
            emit({})
        return 0

    emit({})
    return 0


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception as exc:
        print(json.dumps({"systemMessage": f"Bridge FEM Hook 输入无效：{exc}"}, ensure_ascii=False))
        return 0
    if not isinstance(payload, Mapping):
        print(json.dumps({"systemMessage": "Bridge FEM Hook 输入必须为 JSON object"}, ensure_ascii=False))
        return 0
    return handle_hook(payload)


if __name__ == "__main__":
    raise SystemExit(main())
