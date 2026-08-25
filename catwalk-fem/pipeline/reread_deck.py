"""Independent reread of a CalculiX deck. Does not trust write_inp meta."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from audit_frozen_deck import (
    classify_ic_line,
    count_boundary_cards,
    parse_initial_conditions,
    parse_nset,
)
from constants import N_CROSS_PASSAGES, N_PORTALS_BOTH_DECKS, N_PORTALS_PER_DECK
from formfind import initial_state
from reconcile import sha256_file

FROZEN_SHA256 = "82548e6a3bd2612b6b39a08c313402b32a1961af6eba018158267906276ab6da"
FROZEN_NAME = "zjg_catwalk_coarsened.inp"
PORTAL_UNIT = "榀"
PORTAL_NOT_UNIT = "榌"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def reread_inp(path: Path) -> dict:
    path = Path(path)
    data = path.read_bytes()
    text = data.decode("utf-8")
    ic = parse_initial_conditions(text)
    rows = ic.get("rows") or []
    floor_nodes = parse_nset(text, "N_FLOOR_ANCHOR")
    portal_nodes = parse_nset(text, "N_PORTAL_ANCHOR")
    overlap = sorted(set(floor_nodes) & set(portal_nodes))
    state = initial_state()
    sigma_floor = state["sigma_floor_Pa"]
    sigma_portal = state["sigma_portal_Pa"]
    n_eight = sum(1 for r in rows if r["ccx_2_21_legal"])
    n_elset = sum(1 for r in rows if r["elset_plus_uniaxial"])
    first_tokens = {r["first_token"] for r in rows}
    first_are_int = bool(rows) and all(re.fullmatch(r"-?\d+", r["first_token"] or "") for r in rows)
    # axial PK2 recovered from tensor: for S = σ n⊗n, tr(S) = σ
    traces = []
    for r in rows[: min(len(rows), 24)]:
        if r["n_fields"] == 8:
            try:
                traces.append(sum(float(r["fields"][i]) for i in (2, 3, 4)))
            except ValueError:
                pass
    return {
        "path": str(path),
        "name": path.name,
        "bytes": len(data),
        "sha256": sha256_bytes(data),
        "is_frozen_82548e6a": sha256_bytes(data) == FROZEN_SHA256,
        "heading_has_k16876": "K16+876" in text,
        "has_25556": "255.56" in text,
        "has_00296": "0.0296" in text,
        "has_target_freq_values": any(s in text for s in ("0.0296", "0.0301", "0.1187")),
        "n_floor_anchor": len(floor_nodes),
        "n_portal_anchor": len(portal_nodes),
        "anchor_overlap": len(overlap),
        "anchors_disjoint": len(overlap) == 0,
        "boundary": count_boundary_cards(text),
        "initial_conditions": {
            "present": ic.get("present"),
            "keyword_line": ic.get("keyword_line"),
            "keyword_line_no": ic.get("keyword_line_no"),
            "n_rows": len(rows),
            "n_ccx221_legal": n_eight,
            "n_elset_uniaxial": n_elset,
            "all_ccx221_legal": bool(rows) and n_eight == len(rows),
            "any_elset_uniaxial": n_elset > 0,
            "first_tokens_sample": sorted(first_tokens)[:8],
            "first_tokens_are_element_numbers": first_are_int,
            "first_row": rows[0] if rows else None,
            "trace_sample": traces,
            "trace_matches_sigma_floor": bool(traces) and abs(traces[0] - sigma_floor) / sigma_floor < 1e-5,
            "writer_sigma_floor_Pa": sigma_floor,
            "writer_sigma_portal_Pa": sigma_portal,
        },
        "portal_unit": PORTAL_UNIT,
        "portal_not_unit": PORTAL_NOT_UNIT,
        "expected_passages": N_CROSS_PASSAGES,
        "expected_portals_per_deck": N_PORTALS_PER_DECK,
        "expected_portals_both": N_PORTALS_BOTH_DECKS,
    }


def compare_frozen_untouched(frozen_path: Path) -> dict:
    digest = sha256_file(frozen_path)
    return {
        "path": str(frozen_path),
        "sha256": digest,
        "expected": FROZEN_SHA256,
        "untouched": digest == FROZEN_SHA256,
    }
