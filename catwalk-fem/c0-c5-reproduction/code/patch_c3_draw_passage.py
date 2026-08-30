#!/usr/bin/env python3
"""Apply the drawing-faithful C3 passage cut to the parser-safe deck.

Rule (1225 / report 4.4-4.5, no E20/E21, no 0.0996 back-tune):
- Drop every UCOR6 whose two nodes sit on opposite sides of Y=0.
  Those 189 members are the only finite-element path that locks left UZ to right UZ.
- Keep every same-walkway and same-half-passage UCOR6 (UXYZ framing stays).
- Keep every *EQUATION: none of them cross Y=0.
- Do not touch UCAB3 cables, MASS, boundaries, or frequency request.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from collections import defaultdict
from pathlib import Path

CROSS_Y0 = 0.0
EXPECTED_SRC_SHA256 = "667c504770b99d4a3c484a114e16bb7c048c883d3a004f3e10dd71536f33dc86"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def parse_nodes_and_mark(src: Path):
    coords_y = {}
    drop_eids = set()
    drop_by_elset = defaultdict(int)
    keep_by_elset = defaultdict(int)
    state = ""
    el_type = ""
    elset = ""
    with src.open(encoding="utf-8") as handle:
        for raw in handle:
            line = raw.strip()
            if not line or line.startswith("**"):
                continue
            if line.startswith("*"):
                upper = line.upper()
                state = ""
                if upper.startswith("*NODE") and "FILE" not in upper:
                    state = "node"
                elif upper.startswith("*ELEMENT"):
                    state = "element"
                    el_type = re.search(r"TYPE=([^,\s]+)", upper).group(1)
                    elset = re.search(r"ELSET=([^,\s]+)", upper).group(1)
                continue
            if state == "node":
                fields = [part.strip() for part in line.split(",")]
                coords_y[int(fields[0])] = float(fields[2])
            elif state == "element" and el_type == "UCOR6":
                fields = [part.strip() for part in line.split(",") if part.strip()]
                eid = int(fields[0])
                n1, n2 = int(fields[1]), int(fields[2])
                if coords_y[n1] * coords_y[n2] < CROSS_Y0:
                    drop_eids.add(eid)
                    drop_by_elset[elset] += 1
                else:
                    keep_by_elset[elset] += 1
    if len(drop_eids) != 189:
        raise SystemExit(f"expected 189 Y=0-crossing UCOR6, got {len(drop_eids)}")
    return coords_y, drop_eids, dict(drop_by_elset), dict(keep_by_elset)


def rewrite(src, dst, drop_eids, drop_by_elset, keep_by_elset):
    empty_elsets = {name for name, count in drop_by_elset.items() if keep_by_elset.get(name, 0) == 0}
    stats = {
        "lines_in": 0,
        "lines_out": 0,
        "elements_dropped": 0,
        "element_headers_dropped": 0,
        "user_sections_dropped": 0,
        "elset_cards_dropped": 0,
    }
    state = ""
    el_type = ""
    elset = ""
    pending_header = None
    skip_section_data = False
    with src.open(encoding="utf-8") as handle, dst.open("w", encoding="utf-8", newline="\n") as out:
        def write(text):
            out.write(text)
            stats["lines_out"] += text.count("\n")

        for raw in handle:
            stats["lines_in"] += 1
            stripped = raw.strip()
            upper = stripped.upper()
            if stripped.startswith("*") and not stripped.startswith("**"):
                skip_section_data = False
                if pending_header is not None:
                    pending_header = None
                    stats["element_headers_dropped"] += 1
                if upper.startswith("*ELEMENT"):
                    el_type = re.search(r"TYPE=([^,\s]+)", upper).group(1)
                    elset = re.search(r"ELSET=([^,\s]+)", upper).group(1)
                    state = "element"
                    if el_type == "UCOR6" and elset in empty_elsets:
                        pending_header = raw
                        continue
                    pending_header = raw if el_type == "UCOR6" else None
                    if pending_header is None:
                        write(raw)
                    continue
                if upper.startswith("*USER SECTION"):
                    match = re.search(r"ELSET=([^,\s]+)", upper)
                    section_elset = match.group(1) if match else ""
                    state = "section"
                    if section_elset in empty_elsets:
                        skip_section_data = True
                        stats["user_sections_dropped"] += 1
                        continue
                    write(raw)
                    continue
                if upper.startswith("*ELSET"):
                    match = re.search(r"ELSET=([^,\s]+)", upper)
                    card_elset = match.group(1) if match else ""
                    state = "elset"
                    if card_elset in empty_elsets:
                        skip_section_data = True
                        stats["elset_cards_dropped"] += 1
                        continue
                    write(raw)
                    continue
                state = ""
                write(raw)
                continue
            if skip_section_data:
                continue
            if state == "element" and el_type == "UCOR6":
                fields = [part.strip() for part in stripped.split(",") if part.strip()]
                if fields and int(fields[0]) in drop_eids:
                    stats["elements_dropped"] += 1
                    continue
                if pending_header is not None:
                    write(pending_header)
                    pending_header = None
                write(raw)
                continue
            write(raw)
        if pending_header is not None:
            stats["element_headers_dropped"] += 1
    stats["empty_elsets"] = len(empty_elsets)
    return stats


def main():
    here = Path(__file__).resolve().parent
    repo_root = here.parent if here.name == "code" else here
    src = Path(os.environ.get("C3_SRC", repo_root / "solver" / "c3_ub_frozen_tangent_diag" / "C3-UB-FT14-PARSER-SAFE_m14_667c504770b99d4a.inp"))
    if not src.is_file():
        fallback = here / "C3-UB-FT14-PARSER-SAFE_m14_667c504770b99d4a.inp"
        src = fallback if fallback.is_file() else src
    if not src.is_file():
        raise SystemExit(f"missing source deck: {src}")
    src_sha = sha256_file(src)
    if src_sha != EXPECTED_SRC_SHA256:
        raise SystemExit(f"source SHA mismatch: {src_sha}")
    _, drop_eids, drop_by_elset, keep_by_elset = parse_nodes_and_mark(src)
    default_out = repo_root / "artifacts" if (repo_root / "artifacts").is_dir() else here
    out_dir = Path(os.environ.get("C3_OUT", default_out))
    out_dir.mkdir(parents=True, exist_ok=True)
    dst = out_dir / "C3-UB-FT14-DRAW-PASSAGE_m14.inp"
    stats = rewrite(src, dst, drop_eids, drop_by_elset, keep_by_elset)
    dst_sha = sha256_file(dst)
    receipt = {
        "schema": "catwalk.c3-ub-ft14.draw-passage-patch.v1",
        "source": {"path": src.name, "sha256": src_sha, "bytes": src.stat().st_size},
        "output": {"path": dst.name, "sha256": dst_sha, "bytes": dst.stat().st_size},
        "rule": {
            "drop": "UCOR6 with y1*y2 < 0",
            "keep": "same-sign-Y UCOR6, all EQUATION, all UCAB3, MASS, BOUNDARY",
            "e20_e21_springs": False,
            "back_tuned_to_0_0996": False,
            "target_access": "NONE",
        },
        "dropped_count": len(drop_eids),
        "dropped_by_elset": drop_by_elset,
        "stats": stats,
        "frequency_claim": False,
        "note": "Patch only. Does not re-solve. Cutting Y=0 members softens differential UZ; it cannot raise M3 from 0.07267 Hz to TA1 0.0996 Hz.",
    }
    receipt_path = out_dir / "C3_DRAW_PASSAGE_PATCH.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"event": "C3_DRAW_PASSAGE_PATCHED", "dropped": len(drop_eids), "dst": str(dst), "dst_sha256": dst_sha, "receipt": str(receipt_path)}, sort_keys=True))


if __name__ == "__main__":
    main()
