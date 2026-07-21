#!/usr/bin/env python3
"""Deterministic run-state controller used by N00 and lifecycle hooks."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

from bridge_fem_base import (
    NODE_RE,
    PolicyError,
    atomic_write_json,
    artifact_root,
    contract_snapshot,
    find_repo_root,
    json_dump,
    load_policy,
    load_state,
    resolve_inside,
    sha256_bytes,
    sha256_file,
    state_path,
    utc_now,
)
from bridge_fem_receipts import validate_gate_chain, validate_gate_receipt


def default_run_paths(run_id: str) -> dict[str, str]:
    base = Path(".bridge-fem/runs") / run_id
    return {
        "artifactRoot": (base / "artifacts").as_posix(),
        "gateReceiptRoot": (base / "gate-receipts").as_posix(),
        "taskPacketRoot": (base / "task-packets").as_posix(),
        "nodeReceiptRoot": (base / "node-receipts").as_posix(),
    }


def command_init(args: argparse.Namespace) -> int:
    root = find_repo_root(args.cwd)
    policy = load_policy(root)
    path = state_path(root, policy)
    if path.exists() and not args.force:
        raise PolicyError(f"active run 已存在：{path.relative_to(root)}；使用 close 或 --force")
    mode = args.mode.upper()
    if mode not in {"FORMAL", "RESEARCH"}:
        raise PolicyError("mode 只能为 FORMAL 或 RESEARCH")
    defaults = default_run_paths(args.run_id)
    for value in defaults.values():
        resolve_inside(root, value).mkdir(parents=True, exist_ok=True)
    state: dict[str, Any] = {
        "schemaVersion": "1.0.0",
        "projectId": args.project_id,
        "runId": args.run_id,
        "mode": mode,
        "activeNode": "N00",
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
        "allowResearchSolve": bool(args.allow_research_solve),
        "contractSnapshot": contract_snapshot(root, policy),
        **defaults,
    }
    atomic_write_json(path, state)
    print(json.dumps(state, ensure_ascii=False, indent=2))
    return 0


def command_enter(args: argparse.Namespace) -> int:
    root = find_repo_root(args.cwd)
    policy = load_policy(root)
    state = load_state(root, policy)
    if state is None:
        raise PolicyError("没有 active run，请先 init")
    node_id = args.node.upper()
    if not NODE_RE.fullmatch(node_id):
        raise PolicyError(f"非法节点：{node_id}")
    cfg = policy.get("nodes", {}).get(node_id)
    if not isinstance(cfg, Mapping):
        raise PolicyError(f"policy 未登记节点：{node_id}")
    upstream = list(cfg.get("requiredUpstreamGates", []))
    strict: set[str] = set()
    if state.get("mode") == "FORMAL" and node_id == "N14":
        strict = set(policy.get("formalPolicy", {}).get("strictSolverGates", []))
    errors = validate_gate_chain(root, policy, state, upstream, strict_gates=strict)
    if errors:
        raise PolicyError("节点进入条件未通过：\n- " + "\n- ".join(errors[:30]))
    task_root = resolve_inside(root, state["taskPacketRoot"])
    task_root.mkdir(parents=True, exist_ok=True)
    packet = {
        "schemaVersion": "1.0.0",
        "projectId": state["projectId"],
        "runId": state["runId"],
        "nodeId": node_id,
        "skill": cfg["skill"],
        "expectedGate": cfg["gate"],
        "requiredUpstreamGates": upstream,
        "requiredArtifacts": cfg.get("requiredArtifacts", []),
        "requiredApprovals": cfg.get("requiredApprovals", []),
        "createdAt": utc_now(),
        "contractSnapshotSha256": sha256_bytes(json_dump(state["contractSnapshot"]).encode("utf-8")),
    }
    packet_path = task_root / f"{node_id}.json"
    atomic_write_json(packet_path, packet)
    state = dict(state)
    state["activeNode"] = node_id
    state["taskPacketPath"] = packet_path.relative_to(root).as_posix()
    state["taskPacketSha256"] = sha256_file(packet_path)
    state["updatedAt"] = utc_now()
    if node_id != "N17":
        state.pop("independentCheckPlanSha256", None)
    atomic_write_json(state_path(root, policy), state)
    print(json.dumps(state, ensure_ascii=False, indent=2))
    return 0


def command_freeze_independent_plan(args: argparse.Namespace) -> int:
    root = find_repo_root(args.cwd)
    policy = load_policy(root)
    state = load_state(root, policy)
    if state is None or state.get("activeNode") != "N17":
        raise PolicyError("只有 active N17 run 可以冻结独立复核计划")
    path = resolve_inside(root, args.path)
    if not path.is_file():
        raise PolicyError(f"计划文件不存在：{args.path}")
    expected = artifact_root(root, state) / "N17" / "independent_check_plan.json"
    if path != expected.resolve():
        raise PolicyError(f"计划必须位于 {expected.relative_to(root)}")
    state = dict(state)
    state["independentCheckPlanSha256"] = sha256_file(path)
    state["independentCheckPlanFrozenAt"] = utc_now()
    state["updatedAt"] = utc_now()
    atomic_write_json(state_path(root, policy), state)
    print(state["independentCheckPlanSha256"])
    return 0


def command_status(args: argparse.Namespace) -> int:
    root = find_repo_root(args.cwd)
    policy = load_policy(root)
    state = load_state(root, policy)
    if state is None:
        print("NO_ACTIVE_RUN")
        return 1
    print(json.dumps(state, ensure_ascii=False, indent=2))
    return 0


def command_validate(args: argparse.Namespace) -> int:
    root = find_repo_root(args.cwd)
    policy = load_policy(root)
    state = load_state(root, policy)
    if state is None:
        raise PolicyError("没有 active run")
    _, errors = validate_gate_receipt(root, policy, state, args.gate.upper(), require_strict_pass=args.strict)
    if errors:
        print("FAIL")
        for error in errors:
            print(f"- {error}")
        return 1
    print("PASS")
    return 0


def command_close(args: argparse.Namespace) -> int:
    root = find_repo_root(args.cwd)
    policy = load_policy(root)
    path = state_path(root, policy)
    state = load_state(root, policy)
    if state is None:
        print("NO_ACTIVE_RUN")
        return 0
    archive = resolve_inside(root, policy.get("auditRoot", ".bridge-fem/audit")) / f"closed-{state.get('runId')}.json"
    state = dict(state)
    state["closedAt"] = utc_now()
    state["closeReason"] = args.reason
    atomic_write_json(archive, state)
    path.unlink()
    print(f"CLOSED {state.get('runId')}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="Create an active run and contract snapshot")
    init.add_argument("--project-id", required=True)
    init.add_argument("--run-id", required=True)
    init.add_argument("--mode", default="FORMAL", choices=["FORMAL", "RESEARCH"])
    init.add_argument("--allow-research-solve", action="store_true")
    init.add_argument("--force", action="store_true")
    init.add_argument("--cwd", default=None)
    init.set_defaults(func=command_init)

    enter = sub.add_parser("enter", help="Validate upstream receipts and enter a node")
    enter.add_argument("node")
    enter.add_argument("--cwd", default=None)
    enter.set_defaults(func=command_enter)

    freeze = sub.add_parser("freeze-independent-plan", help="Freeze N17 independent check plan")
    freeze.add_argument("path")
    freeze.add_argument("--cwd", default=None)
    freeze.set_defaults(func=command_freeze_independent_plan)

    status = sub.add_parser("status", help="Print active run state")
    status.add_argument("--cwd", default=None)
    status.set_defaults(func=command_status)

    validate = sub.add_parser("validate-receipt", help="Validate one Gate receipt")
    validate.add_argument("gate")
    validate.add_argument("--strict", action="store_true")
    validate.add_argument("--cwd", default=None)
    validate.set_defaults(func=command_validate)

    close = sub.add_parser("close", help="Archive and close current run")
    close.add_argument("--reason", default="completed_or_cancelled")
    close.add_argument("--cwd", default=None)
    close.set_defaults(func=command_close)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    try:
        args = build_parser().parse_args(argv)
        return int(args.func(args))
    except PolicyError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
