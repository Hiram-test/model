"""Read a CalculiX deck back into the mesh dict write_inp expects.

Used to emit a new main deck from frozen 82548e6a without touching that file
and without re-reading the 77 MB STEP.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

ELSET_ROLE = {
    "E_FLOOR_ROPE": "floor_rope",
    "E_PORTAL_ROPE": "portal_rope",
    "E_HANDRAIL_ROPE": "handrail_rope",
    "E_LONGITUDINAL_OTHER": "longitudinal_other",
    "E_CROSS_PASSAGE": "cross_passage",
    "E_PORTAL_OR_BEAM": "portal_or_beam",
    "E_SHORT_OTHER": "short_other",
}


def _keyword_name(line: str, key: str) -> str | None:
    upper = line.upper()
    token = f"{key}="
    if token not in upper:
        return None
    raw = line[upper.index(token) + len(token) :]
    return raw.split(",")[0].strip()


def _int_tokens(line: str) -> list[int]:
    out: list[int] = []
    for tok in line.replace(",", " ").split():
        if tok.lstrip("+-").isdigit():
            out.append(int(tok))
    return out


def parse_blocks(path: Path) -> dict:
    coords: dict[int, tuple[float, float, float]] = {}
    elements: dict[int, tuple[int, int, str]] = {}
    nsets: dict[str, list[int]] = {}
    elsets: dict[str, list[int]] = {}
    mode = None
    set_name = None
    elem_type = None
    heading: list[str] = []
    with Path(path).open(encoding="utf-8") as handle:
        for raw in handle:
            line = raw.rstrip("\n")
            if not line:
                continue
            if line.startswith("*"):
                if line.startswith("**"):
                    continue
                key = line.split(",")[0].strip().upper()
                if key == "*HEADING":
                    mode = "HEADING"
                    continue
                if key == "*NODE":
                    mode = "NODE"
                    continue
                if key == "*ELEMENT":
                    mode = "ELEMENT"
                    elem_type = "T3D2" if "T3D2" in line.upper() else ("B31" if "B31" in line.upper() else "OTHER")
                    continue
                if key == "*NSET":
                    mode = "NSET"
                    set_name = _keyword_name(line, "NSET")
                    nsets.setdefault(set_name or "", [])
                    continue
                if key == "*ELSET":
                    mode = "ELSET"
                    set_name = _keyword_name(line, "ELSET")
                    elsets.setdefault(set_name or "", [])
                    continue
                if key.startswith("*STEP") or key.startswith("*INITIAL"):
                    break
                mode = None
                continue
            if mode == "HEADING":
                heading.append(line)
            elif mode == "NODE":
                parts = [p.strip() for p in line.split(",")]
                coords[int(parts[0])] = (float(parts[1]), float(parts[2]), float(parts[3]))
            elif mode == "ELEMENT":
                parts = [p.strip() for p in line.split(",")]
                elements[int(parts[0])] = (int(parts[1]), int(parts[2]), elem_type or "OTHER")
            elif mode == "NSET" and set_name:
                nsets[set_name].extend(_int_tokens(line))
            elif mode == "ELSET" and set_name:
                elsets[set_name].extend(_int_tokens(line))
    return {
        "heading": heading,
        "coords": coords,
        "elements": elements,
        "nsets": nsets,
        "elsets": elsets,
    }


def mesh_from_inp(path: Path) -> dict:
    blocks = parse_blocks(path)
    nids = sorted(blocks["coords"])
    if nids != list(range(1, len(nids) + 1)):
        raise ValueError("node ids are not 1..N; write_inp numbering contract broken")
    coords = np.asarray([blocks["coords"][i] for i in nids], float)
    role_of: dict[int, str] = {}
    for elset, role in ELSET_ROLE.items():
        for eid in blocks["elsets"].get(elset, []):
            role_of[eid] = role
    up = set(blocks["nsets"].get("N_UPSTREAM", []))
    dn = set(blocks["nsets"].get("N_DOWNSTREAM", []))
    eids = sorted(blocks["elements"])
    if eids != list(range(1, len(eids) + 1)):
        raise ValueError("element ids are not 1..M; write_inp numbering contract broken")
    n1 = []
    n2 = []
    role = []
    side = []
    missing_role = []
    for eid in eids:
        a_id, b_id, _etype = blocks["elements"][eid]
        n1.append(a_id - 1)
        n2.append(b_id - 1)
        r = role_of.get(eid)
        if r is None:
            missing_role.append(eid)
            r = "short_other"
        role.append(r)
        a_up, b_up = a_id in up, b_id in up
        a_dn, b_dn = a_id in dn, b_id in dn
        if a_up and b_up:
            side.append("upstream")
        elif a_dn and b_dn:
            side.append("downstream")
        elif a_up or b_up:
            side.append("upstream")
        else:
            side.append("downstream")
    if missing_role:
        raise ValueError(f"{len(missing_role)} elements have no role ELSET, first={missing_role[:5]}")
    return {
        "coords": coords,
        "n1": np.asarray(n1, np.int64),
        "n2": np.asarray(n2, np.int64),
        "role": np.asarray(role, object),
        "side": np.asarray(side, object),
        "n_nodes": int(len(nids)),
        "n_elements": int(len(eids)),
        "source_inp": str(path),
        "nsets": {k: len(v) for k, v in blocks["nsets"].items()},
        "elsets": {k: len(v) for k, v in blocks["elsets"].items()},
    }
