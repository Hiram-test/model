#!/usr/bin/env python3
"""Generate the final VM build record and SHA-256 inventory.

This script intentionally does not decide whether the bridge is safe or whether
G3–G6 pass. It summarizes exactly which commands ran in the disposable Ubuntu
VM, their exit codes, and the files they produced. The report is written even
when an earlier stage fails, so failed experiments remain auditable.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--status", required=True)
    args = parser.parse_args()

    run_root = args.run_root.resolve()
    process_dir = run_root / "process"
    process_dir.mkdir(parents=True, exist_ok=True)

    stages: list[dict[str, Any]] = []
    if args.ledger.exists():
        for raw in args.ledger.read_text(encoding="utf-8").splitlines():
            if raw.strip():
                stages.append(json.loads(raw))

    inventory: list[dict[str, Any]] = []
    for path in sorted(p for p in run_root.rglob("*") if p.is_file()):
        if path == process_dir / "artifacts_sha256.json":
            continue
        inventory.append({
            "path": str(path.relative_to(run_root)),
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        })

    inventory_path = process_dir / "artifacts_sha256.json"
    inventory_path.write_text(json.dumps({
        "manifestVersion": "1.0.0",
        "generatedAtUtc": utc_now(),
        "runStatus": args.status,
        "files": inventory,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    contract = load_json(run_root / "contract" / "model_contract.json") or {}
    build_manifest = load_json(run_root / "model" / "freecad_build_manifest.json") or {}
    validation = load_json(run_root / "validation" / "n07_geometry_validation.json") or {}

    lines = [
        "# 扎青吊桥 CAD-003 虚拟机建模过程记录",
        "",
        f"- 生成时间（UTC）：`{utc_now()}`",
        f"- 流水线状态：`{args.status}`",
        f"- GitHub 提交：`{os.environ.get('GITHUB_SHA', 'LOCAL')}`",
        f"- Ubuntu Runner：`{os.environ.get('RUNNER_OS', 'unknown')} / {os.environ.get('RUNNER_ARCH', 'unknown')}`",
        "- 模型用途：图纸证据绑定的总体参考与 FEM 抽象几何；不是加工、施工放样或安全放行成果。",
        "",
        "## 逐步执行记录",
        "",
        "| 步骤 | 说明 | 退出码 | 用时(s) | 日志 |",
        "|---|---|---:|---:|---|",
    ]
    for stage in stages:
        lines.append(
            f"| `{stage.get('stageId','')}` | {stage.get('description','')} | "
            f"{stage.get('exitCode','')} | {stage.get('durationSeconds','')} | "
            f"`{stage.get('logRelpath','')}` |"
        )

    lines.extend([
        "",
        "## 模型摘要",
        "",
        f"- 数值契约 SHA-256：`{build_manifest.get('contractSha256', '未生成')}`",
        f"- FreeCAD 版本：`{build_manifest.get('freecadVersion', '未生成')}`",
        f"- 权威构件根对象：`{build_manifest.get('rootObjectCount', '未生成')}`",
        f"- STEP 显示对象：`{build_manifest.get('displayObjectCount', '未生成')}`",
        f"- 构件计数：`{json.dumps(build_manifest.get('rootCounts', contract.get('expectedCounts', {})), ensure_ascii=False, sort_keys=True)}`",
        f"- 独立校验：`{validation.get('status', '未运行')}`；关键失败数：`{validation.get('criticalFailureCount', '未运行')}`",
        f"- 工程发布状态：`{contract.get('overallEngineeringRelease', '未生成')}`",
        f"- 阻断原因：{contract.get('blockReason', '未生成')}",
        "",
        "## 关键文件",
        "",
        "- `model/Zhaqing_CAD-003.FCStd`：原生 FreeCAD 文档，含证据元数据、参考几何与显示实体。",
        "- `model/Zhaqing_CAD-003-display.step`：显示实体 STEP，供跨软件打开和回读。",
        "- `contract/model_contract.json`：所有数值、来源句柄、公式和有界假定。",
        "- `model/freecad_build_journal.json`：FreeCAD 建模脚本内部里程碑。",
        "- `validation/n07_geometry_validation.json`：在独立 FreeCAD 进程中重新打开 FCStd、重新导入 STEP 后的检查。",
        "- `process/stage_ledger.jsonl` 与 `process/logs/`：每条 VM 命令、起止时间、退出码和原始标准输出。",
        "- `process/artifacts_sha256.json`：本次运行全部文件的 SHA-256 清单。",
        "",
        "## 已知边界",
        "",
        "风缆锚碇平面坐标仍属于 `U-WIND-001` 有界候选；脚本只能建立满足图示长度和角度条件的候选位置，不能将其升级为测量坐标。即使几何与 STEP 回读检查全部通过，工程发布状态仍保持 `BLOCKED`。",
        "",
    ])
    (process_dir / "VM_BUILD_RECORD.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"status": args.status, "stageCount": len(stages), "fileCount": len(inventory)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
