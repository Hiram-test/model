"""Drawing topology reconcile: 21 passages, 142 portals, disjoint anchors.

Geometry source is STEP. Station lists are DRW-B. This module counts what the
mesh already contains and, if a drawing station is missing, inserts a single
centerline beam so the main deck can be audited against 21 / 142. Insertions
are marked DRW-B and never silently mixed with STEP-detected members.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np

try:
    from .constants import (
        ANCHOR_END_BAND_M,
        ANCHOR_MATCH_TOL_M,
        ANCHOR_SPECS,
        DECK_HALF_SPACING,
        N_CROSS_PASSAGES,
        N_PORTALS_BOTH_DECKS,
        N_PORTALS_PER_DECK,
        PASSAGE_LABELS,
        PASSAGE_MATCH_TOL_M,
        PASSAGE_X,
        PERSONNEL_WIDTH_M,
        PORTAL_MATCH_TOL_M,
        PORTAL_X,
    )
except ImportError:
    from constants import (
        ANCHOR_END_BAND_M,
        ANCHOR_MATCH_TOL_M,
        ANCHOR_SPECS,
        DECK_HALF_SPACING,
        N_CROSS_PASSAGES,
        N_PORTALS_BOTH_DECKS,
        N_PORTALS_PER_DECK,
        PASSAGE_LABELS,
        PASSAGE_MATCH_TOL_M,
        PASSAGE_X,
        PERSONNEL_WIDTH_M,
        PORTAL_MATCH_TOL_M,
        PORTAL_X,
    )


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_sha256_sidecar(path: Path) -> dict:
    path = Path(path)
    digest = sha256_file(path)
    sidecar = path.with_suffix(path.suffix + ".sha256")
    sidecar.write_text(f"{digest}  {path.name}\n")
    return {
        "path": str(path),
        "name": path.name,
        "sha256": digest,
        "bytes": path.stat().st_size,
        "sidecar": str(sidecar),
    }


def _mid_delta(mesh: dict) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    coords = mesh["coords"]
    n1 = mesh["n1"]
    n2 = mesh["n2"]
    mid = 0.5 * (coords[n1] + coords[n2])
    delta = coords[n2] - coords[n1]
    length = np.linalg.norm(delta, axis=1)
    return mid, delta, length


def _passage_mask(mesh: dict, mid: np.ndarray, delta: np.ndarray, length: np.ndarray) -> np.ndarray:
    role = mesh["role"]
    dy = np.abs(delta[:, 1])
    geom = (dy >= 15.0) & (length > 20.0)
    return geom | (role == "cross_passage")


def _y_span_at_x(coords: np.ndarray, x: float, tol: float = PASSAGE_MATCH_TOL_M) -> dict:
    near = np.abs(coords[:, 0] - x) < tol
    if not np.any(near):
        return {"hit": False, "n": 0, "y_min": None, "y_max": None, "idx": np.asarray([], dtype=np.int64)}
    idx = np.flatnonzero(near)
    ys = coords[idx, 1]
    return {
        "hit": bool(ys.min() < -15.0 and ys.max() > 15.0),
        "n": int(idx.size),
        "y_min": float(ys.min()),
        "y_max": float(ys.max()),
        "idx": idx,
        "i_min": int(idx[int(np.argmin(ys))]),
        "i_max": int(idx[int(np.argmax(ys))]),
    }


def _portal_mask(mesh: dict, mid: np.ndarray, delta: np.ndarray, length: np.ndarray) -> np.ndarray:
    role = mesh["role"]
    dx = np.abs(delta[:, 0])
    dy = np.abs(delta[:, 1])
    geom = (dx < 4.0) & (dy >= 1.5) & (dy < 15.0) & (length < 20.0)
    return geom | (role == "portal_or_beam")


def reconcile_passages(mesh: dict) -> dict:
    """A passage hits if members OR nodes at that X span both decks in Y.

    The released centerline STEP tessellates each 49.655 m passage into
    ~1.7 m pieces, so a single-element dy>=15 test is the wrong detector.
    """
    mid, delta, length = _mid_delta(mesh)
    pick = _passage_mask(mesh, mid, delta, length)
    xs = mid[pick, 0] if np.any(pick) else np.asarray([], dtype=float)
    stations = []
    n_hit = 0
    for i, px in enumerate(PASSAGE_X):
        near = np.abs(xs - px) < PASSAGE_MATCH_TOL_M
        n_seg = int(near.sum())
        span = _y_span_at_x(mesh["coords"], float(px))
        hit = n_seg > 0 or span["hit"]
        n_hit += int(hit)
        x_mean = None if n_seg == 0 else float(xs[near].mean())
        stations.append(
            {
                "index": i + 1,
                "label": PASSAGE_LABELS[i],
                "x_drawing": float(px),
                "n_segments": n_seg,
                "y_span": {k: span[k] for k in ("hit", "n", "y_min", "y_max")},
                "hit": hit,
                "source": "step_element" if n_seg > 0 else ("step_yspan" if span["hit"] else None),
                "x_mean": x_mean,
                "dx": None if x_mean is None else abs(x_mean - float(px)),
            }
        )
    return {
        "expected": N_CROSS_PASSAGES,
        "n_drawing": len(PASSAGE_X),
        "n_hit": n_hit,
        "n_missing": N_CROSS_PASSAGES - n_hit,
        "missing_x": [s["x_drawing"] for s in stations if not s["hit"]],
        "stations": stations,
        "pass": n_hit == N_CROSS_PASSAGES,
        "detector": "element_dy_or_node_yspan",
    }


def reconcile_portals(mesh: dict) -> dict:
    mid, delta, length = _mid_delta(mesh)
    pick = _portal_mask(mesh, mid, delta, length)
    side = mesh["side"]
    stations = []
    n_hit = 0
    for i, px in enumerate(PORTAL_X):
        rec = {"index": i + 1, "x_drawing": float(px), "sides": {}}
        for sname in ("upstream", "downstream"):
            mask = pick & (side == sname)
            xs = mid[mask, 0] if np.any(mask) else np.asarray([], dtype=float)
            near = np.abs(xs - px) < PORTAL_MATCH_TOL_M
            n_seg = int(near.sum())
            hit = n_seg > 0
            n_hit += int(hit)
            x_mean = None if not hit else float(xs[near].mean())
            rec["sides"][sname] = {
                "n_segments": n_seg,
                "hit": hit,
                "x_mean": x_mean,
                "dx": None if x_mean is None else abs(x_mean - px),
            }
        stations.append(rec)
    return {
        "expected_per_deck": N_PORTALS_PER_DECK,
        "expected_both_decks": N_PORTALS_BOTH_DECKS,
        "n_drawing_per_deck": len(PORTAL_X),
        "n_hit": n_hit,
        "n_missing": N_PORTALS_BOTH_DECKS - n_hit,
        "missing": [
            {"x": s["x_drawing"], "side": sname}
            for s in stations
            for sname, side_rec in s["sides"].items()
            if not side_rec["hit"]
        ],
        "stations": stations,
        "pass": n_hit == N_PORTALS_BOTH_DECKS,
    }


def _family_nodes(mesh: dict, role_name: str) -> np.ndarray:
    role = mesh["role"]
    n1, n2 = mesh["n1"], mesh["n2"]
    pick = role == role_name
    if not np.any(pick):
        return np.asarray([], dtype=np.int64)
    return np.unique(np.concatenate([n1[pick], n2[pick]]))


def _portal_candidate_nodes(mesh: dict) -> np.ndarray:
    """Portal anchors must not reuse floor-rope nodes.

    Classified portal_rope on this STEP is incomplete (main-span high lines
    only). High-Z nodes that are not floor_rope are the family proxy.
    """
    coords = mesh["coords"]
    floor = _family_nodes(mesh, "floor_rope")
    portal = _family_nodes(mesh, "portal_rope")
    floor_z = float(np.median(coords[floor, 2])) if floor.size else 80.0
    high = np.flatnonzero(coords[:, 2] >= floor_z + 1.20)
    if floor.size:
        high = np.setdiff1d(high, floor, assume_unique=False)
    if high.size:
        return high
    return portal


def family_anchor_sets(mesh: dict) -> dict:
    """Pick floor-rope and portal-rope anchors as disjoint families.

    Physical north anchors sit at x<0 and may be outside a truncated STEP.
    In that case the northernmost nodes of each family are recorded as
    STEP-end proxies. Floor and portal sets are never unioned.
    """
    coords = mesh["coords"]
    result = {}
    for spec in ANCHOR_SPECS:
        if spec["family"] == "portal":
            nodes = _portal_candidate_nodes(mesh)
        else:
            nodes = _family_nodes(mesh, spec["role"])
        rec = {
            **spec,
            "node_idx": np.asarray([], dtype=np.int64),
            "n": 0,
            "x_mean": None,
            "dx_to_target": None,
            "mode": "empty",
        }
        if nodes.size == 0:
            result[spec["id"]] = rec
            continue
        xs = coords[nodes, 0]
        target = float(spec["x"])
        lo, hi = float(xs.min()), float(xs.max())
        if target < lo - 5.0:
            chosen = nodes[xs <= lo + ANCHOR_END_BAND_M]
            mode = "step_north_end_proxy"
        elif target > hi + 5.0:
            chosen = nodes[xs >= hi - ANCHOR_END_BAND_M]
            mode = "step_south_end_proxy"
        else:
            chosen = nodes[np.abs(xs - target) < ANCHOR_MATCH_TOL_M]
            mode = "matched_x"
            if chosen.size == 0:
                j = int(np.argmin(np.abs(xs - target)))
                band = nodes[np.abs(xs - xs[j]) <= ANCHOR_END_BAND_M]
                chosen = band if band.size else nodes[j : j + 1]
                mode = "nearest_family_x"
        rec["node_idx"] = np.asarray(chosen, dtype=np.int64)
        rec["n"] = int(chosen.size)
        rec["mode"] = mode
        rec["family_x_span"] = [lo, hi]
        if chosen.size:
            rec["x_mean"] = float(coords[chosen, 0].mean())
            rec["y_mean"] = float(coords[chosen, 1].mean())
            rec["z_mean"] = float(coords[chosen, 2].mean())
            rec["dx_to_target"] = abs(rec["x_mean"] - target)
            rec["x_min"] = float(coords[chosen, 0].min())
            rec["x_max"] = float(coords[chosen, 0].max())
        result[spec["id"]] = rec

    floor_ids = set()
    portal_ids = set()
    for spec in ANCHOR_SPECS:
        idxs = set(int(i) for i in result[spec["id"]]["node_idx"])
        if spec["family"] == "floor":
            floor_ids |= idxs
        else:
            portal_ids |= idxs
    overlap = sorted(floor_ids & portal_ids)
    result["_audit"] = {
        "n_floor": len(floor_ids),
        "n_portal": len(portal_ids),
        "n_overlap": len(overlap),
        "overlap_idx": overlap,
        "disjoint": len(overlap) == 0,
        "rule": "floor and portal anchors must not share a node or NSET",
    }
    return result


def _interp_side_xyz(mesh: dict, x: float, sname: str) -> np.ndarray:
    coords = mesh["coords"]
    n1, n2, role, side = mesh["n1"], mesh["n2"], mesh["role"], mesh["side"]
    pick = (side == sname) & (role == "floor_rope")
    if not np.any(pick):
        pick = side == sname
    if not np.any(pick):
        y0 = DECK_HALF_SPACING if sname == "downstream" else -DECK_HALF_SPACING
        return np.asarray([x, y0, 200.0], dtype=float)
    nodes = np.unique(np.concatenate([n1[pick], n2[pick]]))
    pts = coords[nodes]
    order = np.argsort(pts[:, 0])
    xs = pts[order, 0]
    if x <= xs[0]:
        return pts[order[0]].copy()
    if x >= xs[-1]:
        return pts[order[-1]].copy()
    j = int(np.searchsorted(xs, x))
    a, b = pts[order[j - 1]], pts[order[j]]
    t = 0.0 if b[0] == a[0] else (x - a[0]) / (b[0] - a[0])
    return a + t * (b - a)


def apply_drawing_overlay(mesh: dict, donor_coords: np.ndarray | None = None) -> tuple[dict, dict]:
    """Ensure 21 passages and 142 portals exist, preferring STEP coordinates.

    Passages on the released STEP are tessellated. If `donor_coords` (merged
    STEP points) already span both decks at a station, inject one beam using
    those STEP points instead of inventing a drawing interpolant.
    """
    coords = [row.copy() for row in mesh["coords"]]
    n1 = list(int(i) for i in mesh["n1"])
    n2 = list(int(i) for i in mesh["n2"])
    role = list(mesh["role"])
    side = list(mesh["side"])
    inserted_passages = []
    inserted_portals = []
    recovered_passages = []

    working = {
        "coords": np.asarray(coords, float),
        "n1": np.asarray(n1, np.int64),
        "n2": np.asarray(n2, np.int64),
        "role": np.asarray(role, object),
        "side": np.asarray(side, object),
    }
    passages = reconcile_passages(working)
    portals = reconcile_portals(working)
    donor = None if donor_coords is None else np.asarray(donor_coords, float)

    half_w = 0.5 * PERSONNEL_WIDTH_M

    def add_node(xyz: np.ndarray) -> int:
        coords.append(np.asarray(xyz, float))
        return len(coords) - 1

    for rec in passages["stations"]:
        if rec["hit"] and rec.get("n_segments", 0) > 0:
            continue
        x = rec["x_drawing"]
        source = "DRW-B"
        a = b = None
        if donor is not None:
            span = _y_span_at_x(donor, x)
            if span["hit"]:
                a = donor[span["i_min"]].copy()
                b = donor[span["i_max"]].copy()
                source = "STEP_YSPAN"
        if a is None:
            a = _interp_side_xyz(working, x, "upstream")
            b = _interp_side_xyz(working, x, "downstream")
            a[0] = x
            b[0] = x
        ia, ib = add_node(a), add_node(b)
        n1.append(ia)
        n2.append(ib)
        role.append("cross_passage")
        side.append("cross")
        item = {"label": rec["label"], "x": x, "source": source}
        if source == "STEP_YSPAN":
            recovered_passages.append(item)
        else:
            inserted_passages.append(item)

    working["coords"] = np.asarray(coords, float)

    for rec in portals["stations"]:
        x = rec["x_drawing"]
        for sname, side_rec in rec["sides"].items():
            if side_rec["hit"]:
                continue
            p = _interp_side_xyz(working, x, sname)
            y0 = DECK_HALF_SPACING if sname == "downstream" else -DECK_HALF_SPACING
            a = np.asarray([x, y0 - half_w, p[2]], float)
            b = np.asarray([x, y0 + half_w, p[2]], float)
            ia, ib = add_node(a), add_node(b)
            n1.append(ia)
            n2.append(ib)
            role.append("portal_or_beam")
            side.append(sname)
            inserted_portals.append({"x": x, "side": sname, "source": "DRW-B"})

    out = {
        "coords": np.asarray(coords, float),
        "n1": np.asarray(n1, np.int64),
        "n2": np.asarray(n2, np.int64),
        "role": np.asarray(role, object),
        "side": np.asarray(side, object),
        "n_nodes": len(coords),
        "n_elements": len(n1),
        "target_ds": mesh.get("target_ds"),
    }
    after_p = reconcile_passages(out)
    after_g = reconcile_portals(out)
    audit = {
        "inserted_passages": inserted_passages,
        "recovered_passages": recovered_passages,
        "inserted_portals": inserted_portals,
        "n_inserted_passages": len(inserted_passages),
        "n_recovered_passages": len(recovered_passages),
        "n_inserted_portals": len(inserted_portals),
        "before": {"passages": passages["n_hit"], "portals": portals["n_hit"]},
        "after": {"passages": after_p["n_hit"], "portals": after_g["n_hit"]},
        "passages": after_p,
        "portals": after_g,
        "rule": "prefer STEP Y-span points; insert drawing beams only if a station is absent",
    }
    return out, audit


def serialize_anchors(anchors: dict) -> dict:
    out = {}
    for key, rec in anchors.items():
        if key == "_audit":
            out[key] = rec
            continue
        out[key] = {k: v for k, v in rec.items() if k != "node_idx"}
        out[key]["n"] = rec["n"]
    return out
