"""Coordinate, boundary and load-case self-consistency gates."""

from __future__ import annotations

from pathlib import Path

import numpy as np

try:
    from .constants import (
        DECK_HALF_SPACING,
        PRIMARY_SUPPORTS,
        SADDLE_N,
        SADDLE_S,
        SAG_FORMED_M,
        SUPPORT_MATCH_TOL_M,
    )
    from .coord import write_json
except ImportError:
    from constants import (
        DECK_HALF_SPACING,
        PRIMARY_SUPPORTS,
        SADDLE_N,
        SADDLE_S,
        SAG_FORMED_M,
        SUPPORT_MATCH_TOL_M,
    )
    from coord import write_json


def evaluate_gates(audit: dict, mesh: dict, inp_meta: dict, inp_text: str, topo: dict | None = None) -> dict:
    coords = mesh["coords"]
    checks = []

    def add(name: str, passed: bool, detail: dict) -> None:
        checks.append({"id": name, "pass": bool(passed), **detail})

    add(
        "COORD-G1-units",
        audit.get("transform", {}).get("decision") is not None and audit.get("x_max", 0) < 20_000,
        {"msg": "internal coordinates are metres, not raw millimetres or raw chainage"},
    )
    add(
        "COORD-G2-identity",
        audit.get("transform", {}).get("decision") == "identity"
        and abs(audit.get("transform", {}).get("x_shift_m", 99)) < 1e-9,
        {"transform": audit.get("transform")},
    )
    add(
        "COORD-G3-saddle-align",
        bool(audit.get("transform", {}).get("pass_saddle_align")),
        {"expected": [SADDLE_N["x"], SADDLE_S["x"]], "got": audit.get("transform", {}).get("tower_x_after_m")},
    )
    add(
        "COORD-G4-two-decks",
        bool(audit.get("two_decks")) and abs(abs(audit.get("y_pos_median") or 0) - DECK_HALF_SPACING) < 3.0,
        {"y_pos_median": audit.get("y_pos_median"), "y_neg_median": audit.get("y_neg_median")},
    )
    sag_err = audit.get("sag_abs_err_m")
    add(
        "COORD-G5-formed-sag",
        sag_err is not None and sag_err < 15.0,
        {"sag_geom": audit.get("sag_from_geometry_m"), "sag_report": SAG_FORMED_M, "err": sag_err},
    )
    add(
        "COORD-G6-no-xmin-shift-in-inp",
        inp_meta.get("xmin_shift_used") is False
        and abs(inp_meta["x_min"] - audit["x_min"]) < 20.0,
        {"inp_xmin": inp_meta.get("x_min"), "geom_xmin": audit.get("x_min")},
    )

    primary_ok = True
    for spec in PRIMARY_SUPPORTS:
        rec = inp_meta["supports"][spec["id"]]
        ok = rec["n"] > 0 and rec["dx_max"] is not None and rec["dx_max"] <= SUPPORT_MATCH_TOL_M
        if spec["id"] in {"X0", "X4180"} and rec["n"] == 0:
            # ends may be truncated in STEP; record bounds, do not silently invent nodes
            ok = False
        add(
            f"BC-G-{spec['id']}",
            ok,
            {"n": rec["n"], "x_mean": rec["x_mean"], "dx_max": rec["dx_max"], "target": spec["x"]},
        )
        if spec["id"] in {"NT_SADDLE", "ST_SADDLE"} and not ok:
            primary_ok = False
    add("BC-G-primary-saddles", primary_ok, {"msg": "north/south saddles must have support nodes"})

    loads = inp_meta["loads"]
    floor_len = loads["floor_truss_length_m"]
    extra = loads["extra_dead_npm"]
    add(
        "LC-G-dead-resultant",
        floor_len > 1000.0 and abs(loads["extra_dead_resultant_N"] - extra * floor_len) / max(extra * floor_len, 1.0) < 0.15,
        {"resultant": loads["extra_dead_resultant_N"], "expected": extra * floor_len, "L": floor_len},
    )
    add(
        "LC-G-personnel-resultant",
        abs(loads["personnel_resultant_N"] - loads["personnel_npm"] * floor_len) / max(loads["personnel_npm"] * floor_len, 1.0) < 0.15,
        {"resultant": loads["personnel_resultant_N"], "expected": loads["personnel_npm"] * floor_len},
    )
    add(
        "LC-G-wind-resultant",
        abs(loads["wind_resultant_N"] - loads["wind_npm"] * floor_len) / max(loads["wind_npm"] * floor_len, 1.0) < 0.15,
        {"resultant": loads["wind_resultant_N"], "expected": loads["wind_npm"] * floor_len},
    )
    add("LC-G-keywords-complete", inp_meta.get("complete") is True, {"missing": inp_meta.get("missing_keywords")})
    add("ISO-G-no-target-freq", inp_meta.get("target_freq_in_deck") is False, {})
    add("ISO-G-no-255-sag", "255.56" not in inp_text, {})
    add("ISO-G-heading-convention", "K16+876" in inp_text and "*BOUNDARY" in inp_text, {})
    add(
        "ANCHOR-G-names-separate",
        "N_FLOOR_ANCHOR" in inp_text and "N_PORTAL_ANCHOR" in inp_text and "N_FLOOR_PORTAL" not in inp_text,
        {"msg": "floor and portal anchors must be separately named NSETs"},
    )
    add(
        "ANCHOR-G-disjoint",
        bool(inp_meta.get("anchor_nsets_disjoint", False)),
        {"n_floor": inp_meta.get("n_floor_anchor_nodes"), "n_portal": inp_meta.get("n_portal_anchor_nodes"),
         "audit": (inp_meta.get("anchors") or {}).get("_audit")},
    )
    add(
        "ANCHOR-G-south-families",
        (inp_meta.get("anchors") or {}).get("FLOOR_S", {}).get("n", 0) > 0
        and (inp_meta.get("anchors") or {}).get("PORTAL_S", {}).get("n", 0) > 0,
        {
            "floor_s": (inp_meta.get("anchors") or {}).get("FLOOR_S"),
            "portal_s": (inp_meta.get("anchors") or {}).get("PORTAL_S"),
        },
    )
    floor_s = (inp_meta.get("anchors") or {}).get("FLOOR_S") or {}
    portal_s = (inp_meta.get("anchors") or {}).get("PORTAL_S") or {}
    fx, px = floor_s.get("x_mean"), portal_s.get("x_mean")
    add(
        "ANCHOR-G-not-same-x",
        fx is None or px is None or abs(float(fx) - float(px)) > 5.0,
        {"floor_s_x_mean": fx, "portal_s_x_mean": px,
         "msg": "selected south floor and portal nodes must not collapse to the same x"},
    )
    if topo:
        passages = topo.get("passages") or {}
        portals = topo.get("portals") or {}
        add(
            "TOPO-G-passages-21",
            int(passages.get("n_hit", 0)) == 21,
            {"n_hit": passages.get("n_hit"), "missing": passages.get("missing_x"),
             "inserted": topo.get("n_inserted_passages")},
        )
        add(
            "TOPO-G-portals-142",
            int(portals.get("n_hit", 0)) == 142,
            {"n_hit": portals.get("n_hit"), "n_missing": portals.get("n_missing"),
             "inserted": topo.get("n_inserted_portals")},
        )

    # nodes of N_SUPPORT_ALL must lie near some primary station
    if coords.size:
        xs = coords[:, 0]
        stations = np.asarray([s["x"] for s in PRIMARY_SUPPORTS])
        # any support node from meta
        n_sup = sum(inp_meta["supports"][s["id"]]["n"] for s in PRIMARY_SUPPORTS)
        add("BC-G-support-count", n_sup >= 8, {"n_support_nodes": n_sup})

    passed = all(c["pass"] for c in checks)
    bounded_ok_to_fail = {
        "BC-G-X0",
        "BC-G-X4180",
        "COORD-G5-formed-sag",
    }
    bounded = all(c["pass"] for c in checks if c["id"] not in bounded_ok_to_fail)
    status = "PASS" if passed else ("PASS_WITH_BOUNDS" if bounded else "BLOCKED")
    return {
        "status": status,
        "n_pass": sum(1 for c in checks if c["pass"]),
        "n_fail": sum(1 for c in checks if not c["pass"]),
        "checks": checks,
        "x_convention": "x = chainage - K16+876.000",
        "xmin_shift_forbidden": True,
    }


def dump_gates(path: Path, payload: dict) -> None:
    write_json(path, payload)
