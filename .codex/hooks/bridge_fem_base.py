#!/usr/bin/env python3
"""Shared filesystem, hashing, run-state and contract helpers."""

import datetime as dt
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

POLICY_RELATIVE = Path(".codex/hooks/node_hook_policy.json")
STATE_FALLBACK = Path(".bridge-fem/current.json")
HEX64 = re.compile(r"^[0-9a-fA-F]{64}$")
NODE_RE = re.compile(r"^N(?:0[0-9]|1[0-8])$")
GATE_RE = re.compile(r"^G(?:-ORCH|[0-9]+[A-Z]?)$")
READ_ONLY_SHELL = re.compile(
    r"^\s*(?:pwd|ls(?:\s|$)|dir(?:\s|$)|find(?:\s|$)|findstr(?:\s|$)|"
    r"grep(?:\s|$)|rg(?:\s|$)|cat(?:\s|$)|type(?:\s|$)|head(?:\s|$)|"
    r"tail(?:\s|$)|sed\s+-n(?:\s|$)|Get-Content(?:\s|$)|Test-Path(?:\s|$)|"
    r"git\s+(?:status|diff|show|log|branch|rev-parse)(?:\s|$)|"
    r"sha256sum(?:\s|$)|certutil\s+-hashfile(?:\s|$)|python(?:3)?\s+-m\s+json\.tool(?:\s|$))",
    re.IGNORECASE,
)
MUTATION_TOKENS = re.compile(
    r"(?:^|\s)(?:rm|del|erase|rmdir|mv|move|cp|copy|mkdir|touch|tee|"
    r"Set-Content|Add-Content|Out-File|Remove-Item|Move-Item|Copy-Item|"
    r"New-Item|git\s+(?:add|commit|push|checkout|switch|reset|clean)|"
    r"python(?:3)?\s+[^\n]*\.(?:py|pyw)|py\s+-3\s+[^\n]*\.py)(?:\s|$)",
    re.IGNORECASE,
)
CLAIM_NODE = re.compile(
    r"\b(N(?:0[0-9]|1[0-8]))\b[^\n]{0,60}(完成|已执行|PASS|通过)", re.IGNORECASE
)
CLAIM_GATE = re.compile(r"\b(G(?:-ORCH|[0-9]+[A-Z]?))\b[^\n]{0,60}(PASS|通过)", re.IGNORECASE)


class PolicyError(RuntimeError):
    pass


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def json_dump(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_write_json(path: Path, data: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def find_repo_root(cwd: str | Path | None = None) -> Path:
    start = Path(cwd or os.getcwd()).resolve()
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=start,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            return Path(proc.stdout.strip()).resolve()
    except (OSError, subprocess.SubprocessError):
        pass
    for candidate in (start, *start.parents):
        if (candidate / ".git").exists() or (candidate / "bridge-fem-skill-suite").exists():
            return candidate
    return start


def resolve_inside(root: Path, relative: str | Path) -> Path:
    path = (root / Path(relative)).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError as exc:
        raise PolicyError(f"路径越出仓库：{relative}") from exc
    return path


def load_policy(root: Path) -> dict[str, Any]:
    path = root / POLICY_RELATIVE
    if not path.is_file():
        raise PolicyError(f"缺少 Hook policy：{POLICY_RELATIVE.as_posix()}")
    policy = load_json(path)
    if not isinstance(policy, dict) or not isinstance(policy.get("nodes"), dict):
        raise PolicyError("node_hook_policy.json 格式无效")
    return policy


def state_path(root: Path, policy: Mapping[str, Any]) -> Path:
    return resolve_inside(root, policy.get("stateFile", str(STATE_FALLBACK)))


def load_state(root: Path, policy: Mapping[str, Any]) -> dict[str, Any] | None:
    path = state_path(root, policy)
    if not path.is_file():
        return None
    state = load_json(path)
    if not isinstance(state, dict):
        raise PolicyError("current.json 必须为 JSON object")
    return state


def policy_patterns(policy: Mapping[str, Any], key: str) -> list[re.Pattern[str]]:
    raw = policy.get("patterns", {}).get(key, [])
    return [re.compile(str(item), re.IGNORECASE) for item in raw]


def matches_any(patterns: Iterable[re.Pattern[str]], text: str) -> bool:
    return any(pattern.search(text) for pattern in patterns)


def command_markers(policy: Mapping[str, Any], key: str) -> list[str]:
    return [str(x).lower() for x in policy.get("approvedCommands", {}).get(key, [])]


def contains_marker(text: str, markers: Sequence[str]) -> bool:
    lowered = text.lower().replace("\\", "/")
    return any(marker.lower().replace("\\", "/") in lowered for marker in markers)


def tool_text(payload: Mapping[str, Any]) -> str:
    value = payload.get("tool_input")
    if isinstance(value, Mapping):
        command = value.get("command")
        if isinstance(command, str):
            return command
    try:
        return json.dumps(value, ensure_ascii=False)
    except TypeError:
        return str(value or "")


def tool_is_mutating(tool_name: str, text: str) -> bool:
    if tool_name == "apply_patch":
        return True
    if tool_name == "Bash":
        stripped = text.strip()
        if not stripped:
            return False
        if re.search(r"(?:>>?|\|\s*tee\b|\b2?>&?1\b)", stripped, re.IGNORECASE):
            return True
        if MUTATION_TOKENS.search(stripped):
            return True
        return not bool(READ_ONLY_SHELL.match(stripped))
    if tool_name == "Agent":
        return False
    lowered = tool_name.lower()
    if lowered.startswith("mcp__"):
        return bool(re.search(r"write|edit|create|update|delete|remove|move|copy|upload|commit|push|execute|run", lowered))
    return bool(re.search(r"write|edit|create|update|delete|remove|move|copy|execute|run", lowered))


def normalized_tool_text(payload: Mapping[str, Any]) -> str:
    return tool_text(payload).replace("\\", "/")


def protected_contract_touched(policy: Mapping[str, Any], text: str) -> list[str]:
    normalized = text.replace("\\", "/").lower()
    hits: list[str] = []
    for raw in policy.get("protectedContractFiles", []):
        candidate = str(raw).replace("\\", "/").lower()
        if candidate in normalized:
            hits.append(str(raw))
    for match in re.findall(r"\.codex/hooks/[a-z0-9_.-]+\.py", normalized):
        if match not in hits:
            hits.append(match)
    return hits


def contract_snapshot(root: Path, policy: Mapping[str, Any]) -> dict[str, str]:
    protected = [str(item) for item in policy.get("protectedContractFiles", [])]
    hook_root = root / ".codex/hooks"
    if hook_root.is_dir():
        for path in sorted(hook_root.glob("*.py")):
            relative = path.relative_to(root).as_posix()
            if relative not in protected:
                protected.append(relative)

    result: dict[str, str] = {}
    for relative in protected:
        path = resolve_inside(root, relative)
        if not path.is_file():
            raise PolicyError(f"受保护契约文件缺失：{relative}")
        result[str(relative)] = sha256_file(path)
    return result


def verify_contract_snapshot(root: Path, state: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    snapshot = state.get("contractSnapshot")
    if not isinstance(snapshot, Mapping):
        return ["current.json 缺少 contractSnapshot"]
    for relative, expected in snapshot.items():
        try:
            path = resolve_inside(root, str(relative))
        except PolicyError as exc:
            errors.append(str(exc))
            continue
        if not path.is_file():
            errors.append(f"契约文件被删除：{relative}")
            continue
        actual = sha256_file(path)
        if actual != expected:
            errors.append(f"契约哈希变化：{relative}")
    return errors


def state_context(policy: Mapping[str, Any], state: Mapping[str, Any] | None) -> str:
    if state is None:
        return (
            "Bridge FEM Hook 已启用；当前没有 active run。执行 solver、写 Gate 状态或生成 release 前，"
            "先运行 `python .codex/hooks/bridge_fem_run.py init ...`，随后用 `bridge_fem_run.py enter Nxx` 进入节点。"
        )
    node = str(state.get("activeNode", "UNKNOWN"))
    node_cfg = policy.get("nodes", {}).get(node, {})
    artifacts = ", ".join(node_cfg.get("requiredArtifacts", []))
    upstream = ", ".join(node_cfg.get("requiredUpstreamGates", [])) or "无"
    return (
        f"Bridge FEM active run：project={state.get('projectId')}，run={state.get('runId')}，"
        f"mode={state.get('mode')}，node={node}，expectedGate={node_cfg.get('gate')}。"
        f"进入条件：{upstream}。节点完成前必须生成全部规定工件并由独立 Gate evaluator 计算状态。"
        f"规定工件：{artifacts}。专业节点不得直接填写 Gate PASS。"
    )


def receipt_path(root: Path, state: Mapping[str, Any], gate_id: str) -> Path:
    receipt_root = state.get("gateReceiptRoot")
    if not isinstance(receipt_root, str) or not receipt_root:
        receipt_root = f".bridge-fem/runs/{state.get('runId')}/gate-receipts"
    return resolve_inside(root, Path(receipt_root) / f"{gate_id}.json")


def artifact_root(root: Path, state: Mapping[str, Any]) -> Path:
    raw = state.get("artifactRoot")
    if not isinstance(raw, str) or not raw:
        raw = f".bridge-fem/runs/{state.get('runId')}/artifacts"
    return resolve_inside(root, raw)


def _receipt_check_ids(gate_id: str, count: int) -> set[str]:
    return {f"{gate_id}.{i}" for i in range(1, count + 1)}
