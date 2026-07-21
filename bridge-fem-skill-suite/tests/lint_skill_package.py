#!/usr/bin/env python3
"""Static integrity checks for the bridge FEM Skill Suite.

The linter is intentionally deterministic. It checks package structure, Skill
frontmatter and required sections, workflow references, schema syntax, examples,
and common writing hazards that can create untestable engineering behavior.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import yaml
from jsonschema import Draft202012Validator

REQUIRED_SKILL_SECTIONS = (
    "# 任务",
    "# 输入契约",
    "# 输出工件",
    "# 工作顺序",
    "# 质量门",
    "# 完成检查",
)

BANNED_PATTERNS = {
    "unfinished marker": re.compile(r"\b(?:TODO|TBD|FIXME|XXX)\b", re.IGNORECASE),
    "ambiguous engineering instruction": re.compile(
        r"待确认|视情况而定|建议考虑|应该问题不大|合理即可|差不多|大概即可|酌情处理"
    ),
    "forbidden contrast phrase": re.compile(r"不是.{0,30}而是", re.DOTALL),
}

EXTERNAL_ARTIFACTS = {
    "project_request",
    "source_files",
    "gate_ledger",
    "all_prior_artifacts",
}

EXAMPLE_SCHEMA_MAP = {
    "analysis_charter.example.yaml": "analysis_charter.schema.json",
    "fem_ir_minimal.example.json": "fem_ir.schema.json",
}

@dataclass
class Finding:
    level: str
    code: str
    path: str
    message: str


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_json_or_yaml(path: Path) -> Any:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        return json.loads(text)
    return yaml.safe_load(text)


def parse_frontmatter(text: str, path: Path) -> tuple[dict[str, Any], str]:
    if not text.startswith("---\n"):
        raise ValueError("missing opening YAML frontmatter delimiter")
    marker = text.find("\n---\n", 4)
    if marker < 0:
        raise ValueError("missing closing YAML frontmatter delimiter")
    meta_text = text[4:marker]
    body = text[marker + 5 :]
    meta = yaml.safe_load(meta_text)
    if not isinstance(meta, dict):
        raise ValueError("frontmatter must parse to a mapping")
    return meta, body


def normalized_artifact_token(name: str) -> str:
    return name.lower().replace("-", "_").replace(".json", "").strip()


def contains_artifact_name(body: str, artifact: str) -> bool:
    token = normalized_artifact_token(artifact)
    normalized = body.lower().replace("-", "_")
    return token in normalized


def iter_text_files(root: Path) -> Iterable[Path]:
    suffixes = {".md", ".yaml", ".yml", ".json", ".py", ".txt"}
    for p in root.rglob("*"):
        if p.is_file() and p.suffix.lower() in suffixes:
            yield p


def lint(root: Path) -> tuple[list[Finding], dict[str, Any]]:
    findings: list[Finding] = []
    stats: dict[str, Any] = {
        "skill_count": 0,
        "workflow_node_count": 0,
        "schema_count": 0,
        "example_count": 0,
        "checked_files": 0,
    }

    def add(level: str, code: str, path: Path | str, message: str) -> None:
        rel = str(path.relative_to(root)) if isinstance(path, Path) and path.is_relative_to(root) else str(path)
        findings.append(Finding(level, code, rel, message))

    required_paths = [
        root / "README.md",
        root / "ARCHITECTURE.md",
        root / "IMPLEMENTATION_BLUEPRINT.md",
        root / "workflow.yaml",
        root / "common" / "ARTIFACT_CONTRACT.md",
        root / "schemas" / "artifact_envelope.schema.json",
    ]
    for p in required_paths:
        if not p.exists():
            add("ERROR", "PKG001", p, "required package file is missing")

    # Generic text hygiene.
    for path in iter_text_files(root):
        stats["checked_files"] += 1
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            add("ERROR", "TXT001", path, f"not valid UTF-8: {exc}")
            continue
        if "\t" in text and path.suffix.lower() in {".md", ".yaml", ".yml", ".json"}:
            add("ERROR", "TXT002", path, "tab character found in structured/text artifact")
        for idx, line in enumerate(text.splitlines(), 1):
            if line.rstrip() != line:
                add("WARN", "TXT003", path, f"trailing whitespace at line {idx}")
        if path.parts[-2:] and "skills" in path.parts:
            for label, pattern in BANNED_PATTERNS.items():
                match = pattern.search(text)
                if match:
                    add("ERROR", "SKL009", path, f"{label}: {match.group(0)!r}")

    # Skills.
    skills_dir = root / "skills"
    skill_files = sorted(skills_dir.glob("*/SKILL.md"))
    stats["skill_count"] = len(skill_files)
    if len(skill_files) != 19:
        add("ERROR", "SKL001", skills_dir, f"expected 19 Skills, found {len(skill_files)}")

    skill_by_name: dict[str, dict[str, Any]] = {}
    for path in skill_files:
        text = path.read_text(encoding="utf-8")
        try:
            meta, body = parse_frontmatter(text, path)
        except Exception as exc:
            add("ERROR", "SKL002", path, str(exc))
            continue
        keys = set(meta)
        missing_meta = {"name", "description"} - keys
        if missing_meta:
            add("ERROR", "SKL003", path, f"frontmatter missing keys: {sorted(missing_meta)}")
        extra_meta = keys - {"name", "description"}
        if extra_meta:
            add("WARN", "SKL004", path, f"unexpected frontmatter keys: {sorted(extra_meta)}")
        name = meta.get("name")
        desc = meta.get("description")
        if not isinstance(name, str) or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name):
            add("ERROR", "SKL005", path, f"invalid Skill name: {name!r}")
            continue
        if name in skill_by_name:
            add("ERROR", "SKL006", path, f"duplicate Skill name also used by {skill_by_name[name]['path']}")
        folder_name = path.parent.name
        expected = re.sub(r"^\d{2}-", "", folder_name)
        if name != expected:
            add("ERROR", "SKL007", path, f"frontmatter name {name!r} does not match folder {expected!r}")
        if not isinstance(desc, str) or len(desc.strip()) < 40:
            add("ERROR", "SKL008", path, "description must be a precise trigger statement of at least 40 characters")
        for section in REQUIRED_SKILL_SECTIONS:
            if section not in body:
                add("ERROR", "SKL010", path, f"missing required section {section!r}")
        if len(body.splitlines()) < 65:
            add("WARN", "SKL011", path, "Skill body is unusually short for an engineering gate")
        if not re.search(r"G(?:-ORCH|\d+[A-Z]?)", body):
            add("ERROR", "SKL012", path, "no gate identifier found in Skill body")
        if "sourceRef" not in body and name not in {"bridge-fem-workflow-orchestrator"}:
            add("WARN", "SKL013", path, "Skill does not mention sourceRef/provenance explicitly")
        skill_by_name[name] = {"path": path, "body": body, "meta": meta}

    # Workflow.
    workflow_path = root / "workflow.yaml"
    try:
        workflow = load_json_or_yaml(workflow_path)
    except Exception as exc:
        add("ERROR", "WF001", workflow_path, f"cannot parse workflow: {exc}")
        workflow = {}
    nodes = workflow.get("nodes", []) if isinstance(workflow, dict) else []
    stats["workflow_node_count"] = len(nodes)
    if len(nodes) != 18:
        add("ERROR", "WF002", workflow_path, f"expected 18 processing nodes N01-N18, found {len(nodes)}")

    node_ids: set[str] = set()
    gates: set[str] = set()
    workflow_skill_names: set[str] = set()
    produced_so_far: set[str] = set(EXTERNAL_ARTIFACTS)
    all_produced: set[str] = set()
    for i, node in enumerate(nodes):
        if not isinstance(node, dict):
            add("ERROR", "WF003", workflow_path, f"node index {i} is not a mapping")
            continue
        node_id = node.get("id")
        skill_name = node.get("skill")
        gate = node.get("gate")
        if node_id in node_ids:
            add("ERROR", "WF004", workflow_path, f"duplicate node id {node_id}")
        node_ids.add(node_id)
        if gate in gates:
            add("ERROR", "WF005", workflow_path, f"duplicate gate id {gate}")
        gates.add(gate)
        if skill_name not in skill_by_name:
            add("ERROR", "WF006", workflow_path, f"node {node_id} references missing Skill {skill_name!r}")
        else:
            workflow_skill_names.add(skill_name)
            body = skill_by_name[skill_name]["body"]
            if gate and gate not in body:
                add("ERROR", "WF007", skill_by_name[skill_name]["path"], f"workflow gate {gate} missing from Skill body")
            for output in node.get("produces", []):
                if not contains_artifact_name(body, str(output)):
                    add("ERROR", "WF008", skill_by_name[skill_name]["path"], f"workflow output {output!r} not named in Skill")
        for req in list(node.get("requires", [])) + list(node.get("optional_requires", [])):
            if req not in produced_so_far and req not in EXTERNAL_ARTIFACTS:
                add("ERROR", "WF009", workflow_path, f"node {node_id} requires {req!r} before any prior node produces it")
        outputs = node.get("produces", [])
        for output in outputs:
            if output in all_produced:
                add("ERROR", "WF010", workflow_path, f"artifact {output!r} is produced by more than one workflow node")
            all_produced.add(output)
            produced_so_far.add(output)

    expected_ids = {f"N{i:02d}" for i in range(1, 19)}
    if node_ids != expected_ids:
        add("ERROR", "WF011", workflow_path, f"node ID set mismatch: missing={sorted(expected_ids-node_ids)}, extra={sorted(node_ids-expected_ids)}")
    skill_names_without_orchestrator = set(skill_by_name) - {"bridge-fem-workflow-orchestrator"}
    if workflow_skill_names != skill_names_without_orchestrator:
        add("ERROR", "WF012", workflow_path, f"workflow/Skill mismatch: missing={sorted(skill_names_without_orchestrator-workflow_skill_names)}, extra={sorted(workflow_skill_names-skill_names_without_orchestrator)}")

    # JSON schemas.
    schema_dir = root / "schemas"
    schemas: dict[str, Any] = {}
    for path in sorted(schema_dir.glob("*.schema.json")):
        stats["schema_count"] += 1
        try:
            schema = json.loads(path.read_text(encoding="utf-8"))
            Draft202012Validator.check_schema(schema)
            schemas[path.name] = schema
        except Exception as exc:
            add("ERROR", "SCH001", path, f"invalid JSON Schema: {exc}")
    if stats["schema_count"] < 20:
        add("WARN", "SCH002", schema_dir, f"schema coverage is sparse: {stats['schema_count']} schemas")

    # All JSON/YAML files parse; selected examples validate against their business schema.
    for folder in (root / "examples", root):
        paths = sorted(folder.glob("*.json")) + sorted(folder.glob("*.yaml")) + sorted(folder.glob("*.yml"))
        for path in paths:
            if folder.name == "examples":
                stats["example_count"] += 1
            try:
                instance = load_json_or_yaml(path)
            except Exception as exc:
                add("ERROR", "DAT001", path, f"cannot parse: {exc}")
                continue
            schema_name = EXAMPLE_SCHEMA_MAP.get(path.name)
            if schema_name:
                schema = schemas.get(schema_name)
                if schema is None:
                    add("ERROR", "DAT002", path, f"mapped schema {schema_name} missing")
                else:
                    errors = sorted(Draft202012Validator(schema).iter_errors(instance), key=lambda e: list(e.path))
                    for err in errors:
                        location = "/".join(map(str, err.path)) or "$"
                        add("ERROR", "DAT003", path, f"schema validation at {location}: {err.message}")

    # README coverage of node folders.
    readme = (root / "README.md").read_text(encoding="utf-8") if (root / "README.md").exists() else ""
    for node_id in sorted(node_ids):
        numeric = node_id[1:]
        if re.search(rf"\|\s*{int(numeric):02d}\s*\|", readme) is None:
            add("WARN", "DOC001", root / "README.md", f"node {numeric} absent from node table")

    # Verify no duplicate exact file content in skills.
    content_hashes: dict[str, Path] = {}
    for path in skill_files:
        digest = sha256(path)
        if digest in content_hashes:
            add("ERROR", "SKL014", path, f"exact duplicate of {content_hashes[digest].relative_to(root)}")
        content_hashes[digest] = path

    return findings, stats


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    findings, stats = lint(root)
    errors = [f for f in findings if f.level == "ERROR"]
    warnings = [f for f in findings if f.level == "WARN"]
    if args.json:
        print(json.dumps({
            "root": str(root),
            "stats": stats,
            "errors": [f.__dict__ for f in errors],
            "warnings": [f.__dict__ for f in warnings],
            "passed": not errors,
        }, ensure_ascii=False, indent=2))
    else:
        print(f"Bridge FEM Skill Suite lint: {len(errors)} error(s), {len(warnings)} warning(s)")
        print("Stats:", ", ".join(f"{k}={v}" for k, v in stats.items()))
        for f in findings:
            print(f"[{f.level}] {f.code} {f.path}: {f.message}")
        print("PASS" if not errors else "FAIL")
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
