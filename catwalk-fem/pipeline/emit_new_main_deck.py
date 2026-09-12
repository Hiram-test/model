#!/usr/bin/env python3
"""Emit a new ccx-2.21-legal main deck. Never rewrite frozen 82548e6a."""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from coord import write_json  # noqa: E402
from gates import dump_gates, evaluate_gates  # noqa: E402
from inp_io import mesh_from_inp  # noqa: E402
from reconcile import sha256_file, write_sha256_sidecar  # noqa: E402
from reread_deck import FROZEN_NAME, FROZEN_SHA256, compare_frozen_untouched, reread_inp  # noqa: E402
from write_inp import write_calculix_inp  # noqa: E402

NEW_NAME = "zjg_catwalk_ccx221.inp"


def emit(artifacts: Path, eval_dir: Path) -> dict:
    artifacts = Path(artifacts)
    eval_dir = Path(eval_dir)
    eval_dir.mkdir(parents=True, exist_ok=True)
    frozen = artifacts / FROZEN_NAME
    before = compare_frozen_untouched(frozen)
    if not before["untouched"]:
        raise SystemExit(f"REFUSING: frozen deck is not 82548e6a (got {before['sha256']})")
    frozen_reread = reread_inp(frozen)
    if not frozen_reread["initial_conditions"]["any_elset_uniaxial"]:
        raise SystemExit("REFUSING: expected 82548e6a to stay ELSET+uniaxial")
    mesh = mesh_from_inp(frozen)
    new_path = artifacts / NEW_NAME
    if new_path.resolve() == frozen.resolve():
        raise SystemExit("REFUSING: new deck path equals frozen path")
    meta = write_calculix_inp(mesh, new_path, include_frequency=True)
    after = compare_frozen_untouched(frozen)
    if not after["untouched"]:
        raise SystemExit("REFUSING: emit rewrote 82548e6a")
    new_reread = reread_inp(new_path)
    topo = json.loads((artifacts / "topology_reconcile.json").read_text())
    audit = json.loads((artifacts / "geometry_audit.json").read_text())
    gates = evaluate_gates(audit, mesh, meta, Path(new_path).read_text(), topo)
    dump_gates(artifacts / "coord_gate_ccx221.json", gates)
    write_json(artifacts / "write_inp_meta_ccx221.json", meta)
    write_json(
        artifacts / "main_deck_manifest_ccx221.json",
        {
            "role": "new_main_deck",
            "path": meta["path"],
            "hash": meta.get("hash"),
            "ic_format": meta.get("ic_format"),
            "ic_n_rows": meta.get("ic_n_rows"),
            "complete": meta["complete"],
            "n_nodes": meta["n_nodes"],
            "n_elements": meta["n_elements"],
            "x_convention": "x = chainage - K16+876.000",
            "anchors_disjoint": meta.get("anchor_nsets_disjoint"),
            "frozen_82548e6a_rewritten": False,
            "frozen_sha256": FROZEN_SHA256,
            "gate_status": gates["status"],
        },
    )
    record = {
        "frozen_before": before,
        "frozen_after": after,
        "frozen_untouched": before["untouched"] and after["untouched"],
        "frozen_reread": {
            k: frozen_reread[k]
            for k in (
                "sha256",
                "bytes",
                "is_frozen_82548e6a",
                "initial_conditions",
                "anchors_disjoint",
            )
        },
        "mesh_from_frozen": {
            "n_nodes": mesh["n_nodes"],
            "n_elements": mesh["n_elements"],
            "elsets": mesh["elsets"],
            "nsets": mesh["nsets"],
            "role_counts": {r: int((mesh["role"] == r).sum()) for r in sorted(set(mesh["role"]))},
        },
        "new_deck": new_reread,
        "writer_meta": {
            "ic_format": meta.get("ic_format"),
            "ic_n_rows": meta.get("ic_n_rows"),
            "ic_n_floor_rows": meta.get("ic_n_floor_rows"),
            "ic_n_portal_rows": meta.get("ic_n_portal_rows"),
            "ic_first_row": meta.get("ic_first_row"),
            "complete": meta.get("complete"),
            "hash": meta.get("hash"),
            "anchor_nsets_disjoint": meta.get("anchor_nsets_disjoint"),
        },
        "gates": {"status": gates["status"], "n_pass": gates["n_pass"], "n_fail": gates["n_fail"],
                  "failed": [c["id"] for c in gates["checks"] if not c["pass"]]},
        "pass_new_ic": bool(new_reread["initial_conditions"]["all_ccx221_legal"]),
        "pass_not_elset": not new_reread["initial_conditions"]["any_elset_uniaxial"],
        "pass_new_hash": new_reread["sha256"] != FROZEN_SHA256,
    }
    write_json(eval_dir / "new_deck_reread.json", record)
    write_json(eval_dir / "frozen_82548e6a_reread.json", frozen_reread)
    write_json(eval_dir / "new_deck_manifest.json", record["writer_meta"] | {"reread": new_reread})
    write_sha256_sidecar(new_path)
    return record


def main() -> int:
    record = emit(ROOT / "artifacts", ROOT / "eval")
    print(json.dumps({
        "frozen_untouched": record["frozen_untouched"],
        "new_sha256": record["new_deck"]["sha256"],
        "new_bytes": record["new_deck"]["bytes"],
        "ic_n_rows": record["new_deck"]["initial_conditions"]["n_rows"],
        "all_ccx221_legal": record["new_deck"]["initial_conditions"]["all_ccx221_legal"],
        "any_elset_uniaxial": record["new_deck"]["initial_conditions"]["any_elset_uniaxial"],
        "gate_status": record["gates"]["status"],
        "failed": record["gates"]["failed"],
    }, indent=2))
    ok = (
        record["frozen_untouched"]
        and record["pass_new_ic"]
        and record["pass_not_elset"]
        and record["pass_new_hash"]
        and record["gates"]["status"] in {"PASS", "PASS_WITH_BOUNDS"}
    )
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
