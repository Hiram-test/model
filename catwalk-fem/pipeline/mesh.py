"""Merge coincident nodes and coarsen longitudinal chains."""

from __future__ import annotations

import numpy as np

try:
    from .constants import NODE_MERGE_TOL_M, PRIMARY_SUPPORTS, PASSAGE_X, PORTAL_X
except ImportError:
    from constants import NODE_MERGE_TOL_M, PRIMARY_SUPPORTS, PASSAGE_X, PORTAL_X


def merge_nodes(p1: np.ndarray, p2: np.ndarray, tol: float = NODE_MERGE_TOL_M) -> dict:
    raw = np.vstack([p1, p2])
    # quantize to merge grid
    key = np.round(raw / tol).astype(np.int64)
    _, inverse, counts = np.unique(key, axis=0, return_inverse=True, return_counts=True)
    coords = np.zeros((len(counts), 3), dtype=np.float64)
    np.add.at(coords, inverse, raw)
    coords /= counts[:, None]
    n1 = inverse[: len(p1)]
    n2 = inverse[len(p1) :]
    keep = n1 != n2
    return {
        "coords": coords,
        "n1": n1[keep],
        "n2": n2[keep],
        "keep": keep,
        "n_nodes": int(len(coords)),
        "n_elements_raw": int(np.count_nonzero(keep)),
    }


def _keep_stations(xs: np.ndarray) -> np.ndarray:
    stations = np.asarray(
        [s["x"] for s in PRIMARY_SUPPORTS] + list(PORTAL_X) + list(PASSAGE_X),
        dtype=np.float64,
    )
    keep = np.zeros(len(xs), dtype=bool)
    keep[0] = True
    keep[-1] = True
    for xs0 in stations:
        j = int(np.argmin(np.abs(xs - xs0)))
        if abs(xs[j] - xs0) < 12.0:
            keep[j] = True
    return keep


def coarsen_classified(classified: dict, merged: dict, target_ds: float = 12.0) -> dict:
    keep_mask = classified["keep"] if "keep" in classified else np.ones(len(classified["role"]), dtype=bool)
    # align roles to merged connectivity
    role = classified["role"][merged["keep"]] if len(classified["role"]) == len(merged["keep"]) else classified["role"]
    side = classified["side"][merged["keep"]] if len(classified["side"]) == len(merged["keep"]) else classified["side"]
    n1, n2 = merged["n1"], merged["n2"]
    coords = merged["coords"]

    # If role length mismatches, skip per-element filter
    if len(role) != len(n1):
        role = classified["role"][merged["keep"]]
        side = classified["side"][merged["keep"]]

    adj: list[dict[int, list[int]]] = []
    # build adjacency per (role, side)
    keys = [f"{r}|{s}" for r, s in zip(role, side)]
    groups: dict[str, list[int]] = {}
    for i, key in enumerate(keys):
        groups.setdefault(key, []).append(i)

    new_n1: list[int] = []
    new_n2: list[int] = []
    new_role: list[str] = []
    new_side: list[str] = []

    used_nodes: set[int] = set()

    for key, eids in groups.items():
        rname, sname = key.split("|", 1)
        if rname == "short_other":
            continue
        if rname in {"cross_passage", "portal_or_beam"}:
            for eid in eids:
                new_n1.append(int(n1[eid]))
                new_n2.append(int(n2[eid]))
                new_role.append(rname)
                new_side.append(sname)
                used_nodes.add(int(n1[eid]))
                used_nodes.add(int(n2[eid]))
            continue

        adj_map: dict[int, list[int]] = {}
        for eid in eids:
            a, b = int(n1[eid]), int(n2[eid])
            adj_map.setdefault(a, []).append(b)
            adj_map.setdefault(b, []).append(a)

        seen_e: set[tuple[int, int]] = set()
        starts = [n for n, nb in adj_map.items() if len(nb) != 2] or list(adj_map)
        visited_n = set()
        for start in starts:
            if start in visited_n and len(adj_map.get(start, [])) == 2:
                continue
            for nb0 in adj_map.get(start, []):
                edge = tuple(sorted((start, nb0)))
                if edge in seen_e:
                    continue
                chain = [start, nb0]
                seen_e.add(edge)
                prev, cur = start, nb0
                while True:
                    nxts = [q for q in adj_map.get(cur, []) if q != prev]
                    if len(nxts) != 1:
                        break
                    nxt = nxts[0]
                    e2 = tuple(sorted((cur, nxt)))
                    if e2 in seen_e:
                        break
                    seen_e.add(e2)
                    chain.append(nxt)
                    prev, cur = cur, nxt
                visited_n.update(chain)
                pts = coords[np.asarray(chain)]
                xs = pts[:, 0]
                order = np.argsort(xs)
                chain = [chain[i] for i in order]
                pts = coords[np.asarray(chain)]
                keep = np.zeros(len(chain), dtype=bool)
                keep[0] = keep[-1] = True
                keep |= _keep_stations(pts[:, 0])
                acc = 0.0
                for i in range(1, len(chain)):
                    acc += float(np.linalg.norm(pts[i] - pts[i - 1]))
                    if acc >= target_ds:
                        keep[i] = True
                        acc = 0.0
                kept = [chain[i] for i in range(len(chain)) if keep[i]]
                if len(kept) < 2:
                    kept = [chain[0], chain[-1]]
                for a, b in zip(kept[:-1], kept[1:]):
                    if a == b:
                        continue
                    new_n1.append(int(a))
                    new_n2.append(int(b))
                    new_role.append(rname)
                    new_side.append(sname)
                    used_nodes.add(int(a))
                    used_nodes.add(int(b))

    # compact unused nodes
    used = sorted(used_nodes)
    remap = {old: i for i, old in enumerate(used)}
    compact = coords[np.asarray(used)]
    return {
        "coords": compact,
        "n1": np.asarray([remap[i] for i in new_n1], dtype=np.int64),
        "n2": np.asarray([remap[i] for i in new_n2], dtype=np.int64),
        "role": np.asarray(new_role, dtype=object),
        "side": np.asarray(new_side, dtype=object),
        "n_nodes": int(len(compact)),
        "n_elements": int(len(new_n1)),
        "target_ds": target_ds,
    }
