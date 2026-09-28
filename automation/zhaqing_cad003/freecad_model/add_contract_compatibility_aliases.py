#!/usr/bin/env python3
"""Add corrected compatibility fact IDs required by the legacy candidate builder.

The evidence reconciliation intentionally supersedes several misclassified fact
IDs. The original stage builder still reads those names only to attach source
references to its temporary candidate objects. This adapter restores the names
with *corrected* meanings and values; it never restores the rejected values.

The final stage-10 geometry is driven by the new explicit facts, not these
aliases. Keeping this bridge separate makes the migration visible and removable.
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
OUTPUT_DIR = Path(os.environ.get("ZHAQING_OUT", PARAMS_PATH.parent)).resolve()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def alias_from(source: dict[str, Any], alias_id: str, source_id: str) -> dict[str, Any]:
    result = dict(source)
    result["factId"] = alias_id
    result["compatibilityAlias"] = True
    result["aliasOf"] = source_id
    result["note"] = "Legacy builder metadata alias; final geometry uses the explicit reconciled fact."
    return result


def add_aliases() -> dict[str, Any]:
    if not PARAMS_PATH.exists():
        raise FileNotFoundError(PARAMS_PATH)
    contract = json.loads(PARAMS_PATH.read_text(encoding="utf-8"))
    accepted = contract.get("acceptedFacts")
    if not isinstance(accepted, dict):
        raise ValueError("acceptedFacts is missing or not an object")

    direct_map = {
        "MAIN_ANCHOR_WIDTH_CM": "MAIN_ANCHOR_TRANSVERSE_CM",
        "MAIN_ANCHOR_LENGTH_CM": "MAIN_ANCHOR_LONGITUDINAL_CM",
        "MAIN_ANCHOR_HEIGHT_CM": "MAIN_ANCHOR_TOTAL_HEIGHT_CM",
        "WIND_ATTACH_BEAM_A": "WIND_ATTACH_VIEW_A",
        "WIND_ATTACH_BEAM_B": "WIND_ATTACH_VIEW_B",
        "WIND_ANCHOR_LENGTH_CM": "WIND_ANCHOR_BASE_LENGTH_CM",
        "WIND_ANCHOR_WIDTH_CM": "WIND_ANCHOR_BASE_WIDTH_CM",
    }
    aliases: dict[str, dict[str, Any]] = {}
    for alias_id, source_id in direct_map.items():
        source = accepted.get(source_id)
        if not isinstance(source, dict):
            raise KeyError(f"missing reconciled fact for compatibility alias: {source_id}")
        aliases[alias_id] = alias_from(source, alias_id, source_id)

    base_height = accepted.get("WIND_ANCHOR_BASE_HEIGHT_CM")
    pedestal_height = accepted.get("WIND_ANCHOR_PEDESTAL_HEIGHT_CM")
    if not isinstance(base_height, dict) or not isinstance(pedestal_height, dict):
        raise KeyError("wind-anchor base/pedestal height facts are missing")
    aliases["WIND_ANCHOR_HEIGHT_CM"] = {
        "factId": "WIND_ANCHOR_HEIGHT_CM",
        "value": float(base_height["value"]) + float(pedestal_height["value"]),
        "unit": "cm",
        "raw": f"{base_height['raw']}+{pedestal_height['raw']}",
        "sourceRef": "33-风缆锚碇.dwg:derived:AB3B+AB2C",
        "sourceRefs": [base_height["sourceRef"], pedestal_height["sourceRef"]],
        "compatibilityAlias": True,
        "aliasOf": ["WIND_ANCHOR_BASE_HEIGHT_CM", "WIND_ANCHOR_PEDESTAL_HEIGHT_CM"],
        "note": "Legacy builder metadata alias; final wind anchorage is a stepped base plus pedestal.",
    }

    for alias_id, value in aliases.items():
        accepted[alias_id] = value

    contract["contractCompatibilityAliases"] = {
        "generatedAtUtc": utc_now(),
        "adapter": Path(__file__).name,
        "adapterSha256": sha256_file(Path(__file__)),
        "aliases": aliases,
        "scope": "Temporary source-reference compatibility for build_freecad_model.py candidate stages only.",
    }
    temporary = PARAMS_PATH.with_suffix(PARAMS_PATH.suffix + ".aliases.tmp")
    temporary.write_text(json.dumps(contract, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, PARAMS_PATH)

    report = {
        "schemaVersion": "1.0.0",
        "generatedAtUtc": utc_now(),
        "status": "PASS",
        "aliasCount": len(aliases),
        "aliases": aliases,
        "contractSha256": sha256_file(PARAMS_PATH),
    }
    (OUTPUT_DIR / "contract_compatibility_alias_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return report


def main() -> int:
    try:
        report = add_aliases()
        print(json.dumps({
            "status": report["status"],
            "aliasCount": report["aliasCount"],
            "aliasIds": sorted(report["aliases"]),
            "contractSha256": report["contractSha256"],
        }, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        error = {
            "generatedAtUtc": utc_now(),
            "status": "FAIL",
            "exception": type(exc).__name__,
            "message": str(exc),
            "traceback": traceback.format_exc(),
        }
        (OUTPUT_DIR / "logs").mkdir(parents=True, exist_ok=True)
        (OUTPUT_DIR / "logs" / "contract-compatibility-alias-failure.json").write_text(
            json.dumps(error, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(json.dumps(error, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
