#!/usr/bin/env python3
"""STEP → coordinate gate → complete CalculiX inp. Does not read TARGET-FREQ."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from classify import classify_segments  # noqa: E402
from coord import apply_transform, geometry_audit, infer_x_transform, write_json  # noqa: E402
from formfind import initial_state  # noqa: E402
from gates import dump_gates, evaluate_gates  # noqa: E402
from mesh import coarsen_classified, merge_nodes  # noqa: E402
from parse_step import parse_step  # noqa: E402
from write_inp import write_calculix_inp  # noqa: E402


def run(step_path: Path, artifacts: Path, target_ds: float = 12.0) -> dict:
    artifacts.mkdir(parents=True, exist_ok=True)
    parsed = parse_step(step_path)
    xyz = np.vstack([parsed["p1"], parsed["p2"]])
    transform = infer_x_transform(xyz)
    p1 = apply_transform(parsed["p1"], transform["x_shift_m"])
    p2 = apply_transform(parsed["p2"], transform["x_shift_m"])
    xyz_t = np.vstack([p1, p2])
    audit = geometry_audit(xyz_t, transform)
    write_json(artifacts / "geometry_audit.json", {k: v for k, v in audit.items() if k != "transform"} | {"transform": transform})

    classified = classify_segments(p1, p2)
    write_json(artifacts / "classify_counts.json", classified["counts"])
    merged = merge_nodes(p1, p2)
    classified_kept = {
        "role": classified["role"][merged["keep"]],
        "side": classified["side"][merged["keep"]],
        "keep": merged["keep"],
    }
    mesh = coarsen_classified(classified_kept, merged, target_ds=target_ds)
    write_json(
        artifacts / "mesh_stats.json",
        {
            "n_nodes": mesh["n_nodes"],
            "n_elements": mesh["n_elements"],
            "target_ds": mesh["target_ds"],
            "role_counts": {r: int((mesh["role"] == r).sum()) for r in sorted(set(mesh["role"]))},
        },
    )

    inp_path = artifacts / "zjg_catwalk_coarsened.inp"
    meta = write_calculix_inp(mesh, inp_path, include_frequency=True)
    write_json(artifacts / "write_inp_meta.json", meta)
    write_json(artifacts / "initial_state.json", initial_state())

    gates = evaluate_gates(audit, mesh, meta, Path(meta["path"]).read_text())
    dump_gates(artifacts / "coord_gate.json", gates)
    dump_gates(
        artifacts / "bc_lc_gate.json",
        {
            "status": gates["status"],
            "checks": [c for c in gates["checks"] if c["id"].startswith(("BC-", "LC-"))],
        },
    )

    summary = {
        "step": parsed["path"],
        "sha256": parsed["sha256"],
        "n_segments": parsed["n_segments"],
        "transform": transform,
        "audit_x": [audit["x_min"], audit["x_max"]],
        "mesh": {"n_nodes": mesh["n_nodes"], "n_elements": mesh["n_elements"]},
        "inp": meta["path"],
        "complete_write_inp": meta["complete"],
        "gate_status": gates["status"],
        "n_pass": gates["n_pass"],
        "n_fail": gates["n_fail"],
        "failed": [c["id"] for c in gates["checks"] if not c["pass"]],
    }
    write_json(artifacts / "pipeline_summary.json", summary)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--step",
        type=Path,
        default=Path("/tmp/catwalk-assets/cw_S10_0716t050342_a4_centerline.step"),
    )
    parser.add_argument("--artifacts", type=Path, default=ROOT / "artifacts")
    parser.add_argument("--target-ds", type=float, default=12.0)
    args = parser.parse_args()
    summary = run(args.step, args.artifacts, args.target_ds)
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0 if summary["gate_status"] in {"PASS", "PASS_WITH_BOUNDS"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
