#!/usr/bin/env python3
"""Independent reread of the cleared deck. Does not trust emit meta. No CalculiX."""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from clear_four_b31 import (  # noqa: E402
    CLEARED_BYTES,
    CLEARED_NAME,
    CLEARED_SHA256,
    CLEAR_NSET,
    GIVEN_FOUR,
    SITE_41FB_SHA256,
    SITE_C635_NAME,
    SITE_C635_SHA256,
    describe_unc,
    parse_mesh,
    unconstrained_components,
)
from reread_deck import FROZEN_SHA256, sha256_file  # noqa: E402

FROZEN_41FB_NAME = "zjg_catwalk_ccx221.inp"
FROZEN_82548_NAME = "zjg_catwalk_coarsened.inp"
EXPECTED_IC_ROWS = 421_432
EXPECTED_CROSS_PASSAGE = 42
EXPECTED_DRAWING_STUBS = 28
GIVEN_STUB_X = (-23.895, -44.909, 4225.700)


def parse_elset(path: Path, name: str) -> list[int]:
    ids: list[int] = []
    capture = False
    with Path(path).open(encoding="utf-8") as handle:
        for raw in handle:
            line = raw.rstrip("\n")
            if line.upper().startswith("*ELSET") and f"ELSET={name}".upper() in line.upper():
                capture = True
                continue
            if capture:
                if line.startswith("*"):
                    break
                if line.startswith("**") or not line:
                    continue
                for tok in line.replace(",", " ").split():
                    if tok.lstrip("+-").isdigit():
                        ids.append(int(tok))
    return ids


def stream_ic(path: Path) -> dict:
    n_rows = 0
    n_legal = 0
    n_elset = 0
    first_row = None
    ips_by_eid: dict[int, set[int]] = defaultdict(set)
    started = False
    with Path(path).open(encoding="utf-8") as handle:
        for raw in handle:
            line = raw.rstrip("\n")
            if not started:
                if line.upper().startswith("*INITIAL CONDITIONS") and "STRESS" in line.upper():
                    started = True
                continue
            if not line or line.startswith("**"):
                continue
            if line.startswith("*"):
                break
            parts = [p.strip() for p in line.split(",") if p.strip() != ""]
            n_rows += 1
            if first_row is None:
                first_row = line
            first = parts[0] if parts else ""
            elset_like = bool(first) and first[0].isalpha()
            if elset_like and len(parts) == 2:
                n_elset += 1
            if (not elset_like) and len(parts) == 8:
                n_legal += 1
                try:
                    ips_by_eid[int(first)].add(int(parts[1]))
                except ValueError:
                    pass
    n_with_8 = sum(1 for ips in ips_by_eid.values() if ips == set(range(1, 9)))
    return {
        "n_rows": n_rows,
        "n_ccx221_legal": n_legal,
        "n_elset_uniaxial": n_elset,
        "all_ccx221_legal": n_rows > 0 and n_legal == n_rows,
        "any_elset_uniaxial": n_elset > 0,
        "first_row": first_row,
        "n_elements_with_ic": len(ips_by_eid),
        "n_elements_with_8_ips": n_with_8,
        "all_ic_elements_have_8_ips": n_with_8 == len(ips_by_eid) and len(ips_by_eid) > 0,
    }


def drawing_stub_nodes(mesh: dict) -> dict:
    coords = mesh["coords"]
    deg: dict[int, int] = defaultdict(int)
    for n1, n2, _typ in mesh["elems"].values():
        deg[n1] += 1
        deg[n2] += 1
    stubs = []
    for nid, (x, y, z) in coords.items():
        if any(abs(x - tx) < 1e-6 for tx in GIVEN_STUB_X) and deg.get(nid, 0) == 1:
            stubs.append({"nid": nid, "x": x, "y": y, "z": z, "deg": 1})
    stubs.sort(key=lambda r: (r["x"], r["y"], r["nid"]))
    by_x = {
        f"{tx:.3f}": sum(1 for r in stubs if abs(r["x"] - tx) < 1e-6) for tx in GIVEN_STUB_X
    }
    return {"n": len(stubs), "by_x": by_x, "nids": [r["nid"] for r in stubs]}


def heading_flags(path: Path) -> dict:
    flags = {
        "k16876": False,
        "passages_21": False,
        "portals_142_correct_glyph": False,
        "wrong_glyph_698c": False,
        "clear_nset": False,
        "c635_fail_site": False,
        "not_a_calculation": False,
        "has_00296": False,
        "has_25556": False,
    }
    with Path(path).open(encoding="utf-8") as handle:
        for raw in handle:
            if raw.startswith("*NODE"):
                break
            if "K16+876" in raw:
                flags["k16876"] = True
            if "21 cross-passages" in raw:
                flags["passages_21"] = True
            if "142" in raw and "榀" in raw:
                flags["portals_142_correct_glyph"] = True
            # Heading may name the forbidden glyph only to reject it.
            if "榌" in raw and "not 榌" not in raw and "不是榌" not in raw:
                flags["wrong_glyph_698c"] = True
            if CLEAR_NSET in raw:
                flags["clear_nset"] = True
            if "4-unconstrained-B31 fail site" in raw:
                flags["c635_fail_site"] = True
            if "not a calculation" in raw:
                flags["not_a_calculation"] = True
            if "0.0296" in raw:
                flags["has_00296"] = True
            if "255.56" in raw:
                flags["has_25556"] = True
    return flags


def reread_pair() -> dict:
    artifacts = ROOT / "artifacts"
    frozen = artifacts / FROZEN_82548_NAME
    site41 = artifacts / FROZEN_41FB_NAME
    site_c635 = artifacts / SITE_C635_NAME
    cleared = artifacts / CLEARED_NAME
    hashes = {
        "82548e6a": sha256_file(frozen),
        "41fb3222": sha256_file(site41),
        "c635dad7": sha256_file(site_c635),
        "760c0ee4": sha256_file(cleared),
    }
    bytes_ = {
        "82548e6a": frozen.stat().st_size,
        "41fb3222": site41.stat().st_size,
        "c635dad7": site_c635.stat().st_size,
        "760c0ee4": cleared.stat().st_size,
    }
    mesh_fail = parse_mesh(site_c635)
    unc_fail = unconstrained_components(mesh_fail)
    nodes_fail = sorted({n for c in unc_fail for n in c})
    mesh_ok = parse_mesh(cleared)
    unc_ok = unconstrained_components(mesh_ok)
    ic = stream_ic(cleared)
    ic_fail = stream_ic(site_c635)
    floor = set(mesh_ok["nsets"].get("N_FLOOR_ANCHOR", []))
    portal = set(mesh_ok["nsets"].get("N_PORTAL_ANCHOR", []))
    orphan = mesh_ok["nsets"].get("N_ORPHAN_UNCONSTRAINED", [])
    clear_set = mesh_ok["nsets"].get(CLEAR_NSET, [])
    passage = parse_elset(cleared, "E_CROSS_PASSAGE")
    stubs = drawing_stub_nodes(mesh_ok)
    n_t3d2 = sum(1 for _n1, _n2, typ in mesh_ok["elems"].values() if typ == "T3D2")
    n_b31 = sum(1 for _n1, _n2, typ in mesh_ok["elems"].values() if typ == "B31")
    rec = {
        "role": "independent_reread",
        "trusts_emit_meta": False,
        "ccx_ran": False,
        "pushed": False,
        "merged": False,
        "hashes": hashes,
        "bytes": bytes_,
        "frozen_untouched": {
            "82548e6a": hashes["82548e6a"] == FROZEN_SHA256,
            "41fb3222": hashes["41fb3222"] == SITE_41FB_SHA256,
            "c635dad7": hashes["c635dad7"] == SITE_C635_SHA256,
        },
        "cleared_matches_lock": hashes["760c0ee4"] == CLEARED_SHA256
        and bytes_["760c0ee4"] == CLEARED_BYTES,
        "c635_fail_site": {
            "n_unconstrained_components": len(unc_fail),
            "n_unconstrained_nodes": len(nodes_fail),
            "nodes": nodes_fail,
            "match_given_nodes": nodes_fail == GIVEN_FOUR["nodes"],
            "desc": describe_unc(mesh_fail, unc_fail),
            "has_clear_nset": CLEAR_NSET in mesh_fail["nsets"],
            "ic_n_rows": ic_fail["n_rows"],
            "ic_n_elset": ic_fail["n_elset_uniaxial"],
        },
        "cleared": {
            "n_nodes": len(mesh_ok["coords"]),
            "n_elements": len(mesh_ok["elems"]),
            "n_t3d2": n_t3d2,
            "n_b31": n_b31,
            "n_unconstrained_components": len(unc_ok),
            "after_unc": describe_unc(mesh_ok, unc_ok),
            "n_floor_anchor": len(floor),
            "n_portal_anchor": len(portal),
            "floor_portal_overlap": len(floor & portal),
            "anchors_disjoint": len(floor & portal) == 0,
            "n_orphan": len(orphan),
            "clear_nset": sorted(clear_set),
            "clear_nset_match": sorted(clear_set) == GIVEN_FOUR["nodes"],
            "bc_sets": mesh_ok["bc_sets"],
            "e_cross_passage": len(passage),
            "e_cross_passage_ids": passage,
            "drawing_stubs": stubs,
            "heading": heading_flags(cleared),
            "ic": ic,
            "ic_rows_match_421432": ic["n_rows"] == EXPECTED_IC_ROWS,
            "ic_unchanged_vs_c635": ic["n_rows"] == ic_fail["n_rows"]
            and ic["first_row"] == ic_fail["first_row"],
            "eight_ips": ic["all_ic_elements_have_8_ips"]
            and ic["n_elements_with_ic"] == n_t3d2 + n_b31,
        },
        "expected": {
            "ic_rows": EXPECTED_IC_ROWS,
            "e_cross_passage": EXPECTED_CROSS_PASSAGE,
            "drawing_stubs": EXPECTED_DRAWING_STUBS,
            "clear_nodes": GIVEN_FOUR["nodes"],
        },
    }
    rec["pass"] = (
        rec["frozen_untouched"]["82548e6a"]
        and rec["frozen_untouched"]["41fb3222"]
        and rec["frozen_untouched"]["c635dad7"]
        and rec["cleared_matches_lock"]
        and rec["c635_fail_site"]["n_unconstrained_components"] == 4
        and rec["c635_fail_site"]["match_given_nodes"]
        and rec["cleared"]["n_unconstrained_components"] == 0
        and rec["cleared"]["anchors_disjoint"]
        and rec["cleared"]["clear_nset_match"]
        and rec["cleared"]["e_cross_passage"] == EXPECTED_CROSS_PASSAGE
        and rec["cleared"]["drawing_stubs"]["n"] == EXPECTED_DRAWING_STUBS
        and rec["cleared"]["ic_rows_match_421432"]
        and rec["cleared"]["ic"]["all_ccx221_legal"]
        and not rec["cleared"]["ic"]["any_elset_uniaxial"]
        and rec["cleared"]["eight_ips"]
        and rec["cleared"]["heading"]["k16876"]
        and rec["cleared"]["heading"]["passages_21"]
        and rec["cleared"]["heading"]["portals_142_correct_glyph"]
        and not rec["cleared"]["heading"]["wrong_glyph_698c"]
        and rec["ccx_ran"] is False
        and rec["pushed"] is False
        and rec["merged"] is False
    )
    return rec


if __name__ == "__main__":
    rec = reread_pair()
    out = ROOT / "eval" / "INDEPENDENT_REREAD_760c0ee4.json"
    out.write_text(json.dumps(rec, indent=2) + "\n")
    print(
        json.dumps(
            {
                "pass": rec["pass"],
                "hashes": rec["hashes"],
                "c635_unc": rec["c635_fail_site"]["n_unconstrained_components"],
                "cleared_unc": rec["cleared"]["n_unconstrained_components"],
                "ic_n_rows": rec["cleared"]["ic"]["n_rows"],
                "e_cross_passage": rec["cleared"]["e_cross_passage"],
                "drawing_stubs": rec["cleared"]["drawing_stubs"]["n"],
                "eight_ips": rec["cleared"]["eight_ips"],
                "ccx_ran": rec["ccx_ran"],
            },
            indent=2,
        )
    )
