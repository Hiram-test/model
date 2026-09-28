#!/usr/bin/env python3
"""Assemble independent FCStd, STEP and contract checks into final receipts.

This script is intentionally plain CPython: it cannot modify BReps. It only
combines already sealed JSON reports, verifies their statuses and hashes the
files that were actually read by separate FreeCADCmd processes.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PARAMS_PATH = Path(os.environ.get("ZHAQING_PARAMS", "frozen_model_contract.json")).resolve()
OUTPUT_DIR = Path(os.environ.get("ZHAQING_OUT", "build/zhaqing-cad003/freecad")).resolve()
FCSTD_PATH = OUTPUT_DIR / "Zhaqing_CAD-003.FCStd"
STEP_PATH = OUTPUT_DIR / "Zhaqing_CAD-003-display.step"
ROUNDTRIP_PATH = OUTPUT_DIR / "Zhaqing_CAD-003-STEP-roundtrip.FCStd"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(name: str) -> dict[str, Any]:
    path = OUTPUT_DIR / name
    if not path.exists():
        raise FileNotFoundError(path)
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def assemble() -> tuple[dict[str, Any], dict[str, Any]]:
    params = json.loads(PARAMS_PATH.read_text(encoding="utf-8"))
    fcstd = read_json("fcstd_validation_report.json")
    step = read_json("step_roundtrip_report.json")
    anchor_wind = read_json("anchor_wind_geometry_audit.json")
    penetration = read_json("forbidden_penetration_audit.json")

    source_reports = {
        "nativeFcstd": fcstd,
        "stepRoundtrip": step,
        "anchorWindGeometry": anchor_wind,
        "forbiddenPenetration": penetration,
    }
    checks: list[dict[str, Any]] = []
    for source_name, source in source_reports.items():
        checks.append({
            "checkId": f"SOURCE_REPORT_{source_name.upper()}_PASS",
            "status": "PASS" if source.get("status") == "PASS" else "FAIL",
            "details": {
                "sourceReport": source_name,
                "sourceStatus": source.get("status"),
                "failedChecks": source.get("failedChecks", []),
            },
        })
        for check in source.get("checks", []):
            row = dict(check)
            row["sourceReport"] = source_name
            checks.append(row)

    files_exist = all(path.exists() and path.stat().st_size > 0 for path in (FCSTD_PATH, STEP_PATH, ROUNDTRIP_PATH))
    checks.append({
        "checkId": "FINAL_MODEL_FILES_EXIST",
        "status": "PASS" if files_exist else "FAIL",
        "details": {
            "fcstd": str(FCSTD_PATH),
            "step": str(STEP_PATH),
            "roundtripFcstd": str(ROUNDTRIP_PATH),
        },
    })
    engineering_blocked = params.get("engineeringReleaseStatus") == "BLOCKED"
    checks.append({
        "checkId": "ENGINEERING_BLOCKERS_PROPAGATED",
        "status": "PASS" if engineering_blocked and bool(params.get("blockingIssueIds")) else "FAIL",
        "details": {
            "engineeringReleaseStatus": params.get("engineeringReleaseStatus"),
            "blockingIssueIds": params.get("blockingIssueIds", []),
        },
    })

    technical_pass = all(check.get("status") == "PASS" for check in checks)
    report = {
        "schemaVersion": "1.0.0",
        "generatedAtUtc": utc_now(),
        "technicalStatus": "PASS" if technical_pass else "FAIL",
        "engineeringReleaseStatus": params.get("engineeringReleaseStatus", "BLOCKED"),
        "validationArchitecture": {
            "nativeFcstdProcess": "validate_fcstd_geometry.py",
            "stepRoundtripProcess": "validate_step_roundtrip_direct.py using Part.TopoShape.read",
            "receiptAssembler": Path(__file__).name,
            "reasonForSplit": "Avoid FreeCAD 0.19 crash/memory path from holding native FCStd and expanded 675-solid STEP in one process.",
        },
        "files": {
            "fcstd": {"path": str(FCSTD_PATH), "sha256": sha256_file(FCSTD_PATH), "bytes": FCSTD_PATH.stat().st_size},
            "step": {"path": str(STEP_PATH), "sha256": sha256_file(STEP_PATH), "bytes": STEP_PATH.stat().st_size},
            "stepRoundtrip": {"path": str(ROUNDTRIP_PATH), "sha256": sha256_file(ROUNDTRIP_PATH), "bytes": ROUNDTRIP_PATH.stat().st_size},
        },
        "statistics": {
            **fcstd.get("statistics", {}),
            "step": step.get("statistics", {}),
            "anchorWind": anchor_wind.get("summary", {}),
        },
        "checks": checks,
        "failedChecks": [check["checkId"] for check in checks if check.get("status") != "PASS"],
        "sourceReportFiles": {
            "nativeFcstd": "fcstd_validation_report.json",
            "stepRoundtrip": "step_roundtrip_report.json",
            "anchorWindGeometry": "anchor_wind_geometry_audit.json",
            "forbiddenPenetration": "forbidden_penetration_audit.json",
        },
    }

    gate_receipt = {
        "schemaVersion": "1.0.0",
        "generatedAtUtc": utc_now(),
        "runId": params.get("runId"),
        "technicalGeometryValidation": report["technicalStatus"],
        "gates": [
            {
                "gateId": "G3",
                "status": "BLOCKED",
                "reason": "Complete coordinate transforms, point-by-point round-trip overlays and unique terrain-controlled wind-anchor coordinates are not closed.",
                "blockingIssues": ["U-WIND-001", "C-WIND-ATTACH-NUMBER-001", "C-WIND-HORIZONTAL-ANGLE-001"],
            },
            {
                "gateId": "G4",
                "status": "BLOCKED",
                "reason": "Major systems are modelled, but complete manufacturing-Part mapping, formal assembly graph and orphan audit are not closed.",
                "blockingIssues": ["N05-PART-COVERAGE-INCOMPLETE"],
            },
            {
                "gateId": "G5",
                "status": "BLOCKED",
                "reason": "Display representations are fixed, while anchor hardware, hanger clamps, wind-cable interfaces and terrain coordinates retain high-sensitivity assumptions.",
                "blockingIssues": params.get("blockingIssueIds", []),
            },
            {
                "gateId": "G6",
                "status": "BLOCKED",
                "reason": "Native FCStd and STEP technical geometry can pass, but upstream G3-G5 remain blocked and formal drawing overlays are incomplete.",
                "blockingIssues": ["UPSTREAM-GATES-BLOCKED"],
            },
        ],
        "allowedUse": ["整体装配查看", "STEP交换测试", "后续证据回投与FEM几何接口开发"],
        "forbiddenUse": ["施工放样", "加工下料", "工程量", "正式结构计算", "安全结论"],
    }
    return report, gate_receipt


def write_markdown(report: dict[str, Any]) -> None:
    lines = [
        "# CAD-003 分进程独立技术校验",
        "",
        f"- 技术状态：`{report['technicalStatus']}`",
        f"- 工程发布状态：`{report['engineeringReleaseStatus']}`",
        "- FCStd 和 STEP 在两个独立 FreeCADCmd 进程中读取；STEP 使用 `Part.TopoShape.read`。",
        "- 技术通过不改变 G3–G6 的工程阻断。",
        "",
        "| 检查 | 来源 | 状态 |",
        "|---|---|---|",
    ]
    for check in report["checks"]:
        lines.append(f"| `{check['checkId']}` | {check.get('sourceReport', 'assembler')} | {check['status']} |")
    lines += [
        "",
        "## 说明",
        "",
        "分进程不是降低检查：它隔离了 FreeCAD 0.19 的内存和导入器展开路径。",
        "最终 receipt 仍要求原生 BRep、STEP BRep、包围盒、体积、构件数量、",
        "锚碇/风缆专项几何和禁止穿透全部通过。",
    ]
    (OUTPUT_DIR / "VALIDATION_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    try:
        report, gate_receipt = assemble()
        (OUTPUT_DIR / "validation_report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        (OUTPUT_DIR / "gate_receipt.json").write_text(
            json.dumps(gate_receipt, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        write_markdown(report)
        print(json.dumps({
            "technicalStatus": report["technicalStatus"],
            "engineeringReleaseStatus": report["engineeringReleaseStatus"],
            "failedChecks": report["failedChecks"],
            "validationArchitecture": report["validationArchitecture"],
        }, ensure_ascii=False, indent=2))
        return 0 if report["technicalStatus"] == "PASS" else 1
    except Exception as exc:
        error = {
            "generatedAtUtc": utc_now(),
            "status": "FAIL",
            "exception": type(exc).__name__,
            "message": str(exc),
            "traceback": traceback.format_exc(),
        }
        (OUTPUT_DIR / "logs").mkdir(parents=True, exist_ok=True)
        (OUTPUT_DIR / "logs" / "validation-assembly-failure.json").write_text(
            json.dumps(error, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(json.dumps(error, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
