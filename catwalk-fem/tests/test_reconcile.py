"""21 passages, 142 portals, disjoint floor/portal anchors. No STEP required."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parents[1] / "pipeline"
sys.path.insert(0, str(HERE))

from constants import (  # noqa: E402
    FLOOR_ANCHOR_N,
    FLOOR_ANCHOR_S,
    N_CROSS_PASSAGES,
    N_PORTALS_BOTH_DECKS,
    N_PORTALS_PER_DECK,
    PASSAGE_X,
    PORTAL_ANCHOR_N,
    PORTAL_ANCHOR_S,
    PORTAL_X,
)
from reconcile import apply_drawing_overlay, family_anchor_sets, reconcile_passages, reconcile_portals  # noqa: E402


def test_drawing_counts():
    assert len(PORTAL_X) == N_PORTALS_PER_DECK == 71
    assert len(PASSAGE_X) == N_CROSS_PASSAGES == 21
    assert N_PORTALS_BOTH_DECKS == 142
    assert FLOOR_ANCHOR_N["x"] != PORTAL_ANCHOR_N["x"]
    assert FLOOR_ANCHOR_S["x"] != PORTAL_ANCHOR_S["x"]
    assert abs(FLOOR_ANCHOR_S["x"] - PORTAL_ANCHOR_S["x"]) > 10.0


def _full_station_mesh():
    coords = []
    n1 = []
    n2 = []
    role = []
    side = []
    for s, y0 in (("upstream", -21.45), ("downstream", 21.45)):
        for x in PORTAL_X:
            a = len(coords)
            coords.append((x, y0 - 2.0, 200.0))
            coords.append((x, y0 + 2.0, 200.0))
            n1.append(a)
            n2.append(a + 1)
            role.append("portal_or_beam")
            side.append(s)
        xs_floor = np.unique(np.concatenate([
            np.linspace(-20.0, 4210.368, 40),
            [-23.895, 4210.368],
        ]))
        xs_portal = np.unique(np.concatenate([
            np.linspace(-44.909, 4225.700, 40),
            [-44.909, 4225.700],
        ]))
        base = len(coords)
        for x in xs_floor:
            coords.append((x, y0 + 2.67, 180.0))
        for i in range(len(xs_floor) - 1):
            n1.append(base + i)
            n2.append(base + i + 1)
            role.append("floor_rope")
            side.append(s)
        pbase = len(coords)
        for x in xs_portal:
            coords.append((x, y0 + 3.2, 188.0))
        for i in range(len(xs_portal) - 1):
            n1.append(pbase + i)
            n2.append(pbase + i + 1)
            role.append("portal_rope")
            side.append(s)
    for x in PASSAGE_X:
        a = len(coords)
        coords.append((x, -21.45, 200.0))
        coords.append((x, 21.45, 200.0))
        n1.append(a)
        n2.append(a + 1)
        role.append("cross_passage")
        side.append("downstream")
    return {
        "coords": np.asarray(coords, float),
        "n1": np.asarray(n1, np.int64),
        "n2": np.asarray(n2, np.int64),
        "role": np.asarray(role, object),
        "side": np.asarray(side, object),
    }


def test_reconcile_full_stations():
    mesh = _full_station_mesh()
    passages = reconcile_passages(mesh)
    portals = reconcile_portals(mesh)
    assert passages["n_hit"] == 21
    assert passages["pass"]
    assert portals["n_hit"] == 142
    assert portals["pass"]


def test_overlay_fills_missing_only():
    empty = {
        "coords": np.asarray([[0.0, -21.45, 120.0], [4180.0, -21.45, 120.0],
                              [0.0, 21.45, 120.0], [4180.0, 21.45, 120.0]], float),
        "n1": np.asarray([0, 2], np.int64),
        "n2": np.asarray([1, 3], np.int64),
        "role": np.asarray(["floor_rope", "floor_rope"], object),
        "side": np.asarray(["upstream", "downstream"], object),
        "target_ds": 12.0,
    }
    out, audit = apply_drawing_overlay(empty)
    assert audit["after"]["passages"] == 21
    assert audit["after"]["portals"] == 142
    assert audit["n_inserted_passages"] == 21
    assert audit["n_inserted_portals"] == 142
    assert reconcile_passages(out)["pass"]
    assert reconcile_portals(out)["pass"]


def test_floor_portal_anchors_disjoint():
    mesh = _full_station_mesh()
    anchors = family_anchor_sets(mesh)
    assert anchors["_audit"]["disjoint"]
    assert anchors["FLOOR_S"]["n"] > 0
    assert anchors["PORTAL_S"]["n"] > 0
    assert abs(anchors["FLOOR_S"]["x_mean"] - anchors["PORTAL_S"]["x_mean"]) > 5.0
    floor_nodes = set(int(i) for i in anchors["FLOOR_S"]["node_idx"]) | set(int(i) for i in anchors["FLOOR_N"]["node_idx"])
    portal_nodes = set(int(i) for i in anchors["PORTAL_S"]["node_idx"]) | set(int(i) for i in anchors["PORTAL_N"]["node_idx"])
    assert floor_nodes.isdisjoint(portal_nodes)


if __name__ == "__main__":
    test_drawing_counts()
    test_reconcile_full_stations()
    test_overlay_fills_missing_only()
    test_floor_portal_anchors_disjoint()
    print("test_reconcile ok")
