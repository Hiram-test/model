#!/usr/bin/env python3
"""Pin the 4 leftover unconstrained B31 components on a COPY of c635dad7.

Does not rewrite zjg_catwalk_main.inp (c635dad7 fail site),
zjg_catwalk_ccx221.inp (41fb3222), or zjg_catwalk_coarsened.inp (82548e6a).
Does not run CalculiX.
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
if str(HERE) not in __import__("sys").path:
    __import__("sys").path.insert(0, str(HERE))

from reread_deck import FROZEN_SHA256, sha256_file  # noqa: E402

SITE_41FB_SHA256 = "41fb32225489b0c6f993d3a077ce9293d472e4ede5ff644ca170bebbbbca924a"
SITE_C635_SHA256 = "c635dad78661e6495bdf829b0c97f8610b5fedb8603307e806860032a70cda84"
SITE_C635_NAME = "zjg_catwalk_main.inp"
CLEARED_NAME = "zjg_catwalk_cleared.inp"
CLEARED_SHA256 = "760c0ee44d7077ddfb84273cba916abb1fea1eb2a0ff6cfe57abaec9b0585de9"
CLEARED_BYTES = 47_948_916
CLEAR_NSET = "N_CLEAR_FOUR_B31"

# Independent reread of c635dad7 (this run). 12 nodes, 4 components, B31 only.
GIVEN_FOUR = {
    "n_unconstrained_components": 4,
    "n_nodes": 12,
    "types": ["B31"],
    "x_clusters": ["656", "2965-2968"],
    "nodes": [9518, 9519, 9520, 9521, 33168, 33169, 33170, 33171, 33172, 33173, 33174, 33175],
    "elements": [25520, 26301, 26302, 27932, 28713, 28714, 51698, 51699],
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def parse_mesh(path: Path) -> dict:
    coords: dict[int, tuple[float, float, float]] = {}
    elems: dict[int, tuple[int, int, str]] = {}
    nsets: dict[str, list[int]] = {}
    bc_sets: list[str] = []
    mode = None
    set_name = None
    elem_type = None
    with Path(path).open(encoding="utf-8") as handle:
        for raw in handle:
            line = raw.rstrip("\n")
            if not line:
                continue
            if line.startswith("*"):
                if line.startswith("**"):
                    continue
                key = line.split(",")[0].strip().upper()
                if key == "*NODE":
                    mode = "NODE"
                    continue
                if key == "*ELEMENT":
                    mode = "ELEMENT"
                    elem_type = (
                        "T3D2" if "T3D2" in line.upper() else ("B31" if "B31" in line.upper() else "OTHER")
                    )
                    continue
                if key == "*NSET":
                    mode = "NSET"
                    up = line.upper()
                    set_name = line[up.index("NSET=") + 5 :].split(",")[0].strip()
                    nsets.setdefault(set_name, [])
                    continue
                if key == "*BOUNDARY":
                    mode = "BOUNDARY"
                    continue
                if key.startswith("*STEP") or key.startswith("*INITIAL"):
                    break
                mode = None
                continue
            if mode == "NODE":
                parts = [x.strip() for x in line.split(",")]
                coords[int(parts[0])] = (float(parts[1]), float(parts[2]), float(parts[3]))
            elif mode == "ELEMENT":
                parts = [x.strip() for x in line.split(",")]
                elems[int(parts[0])] = (int(parts[1]), int(parts[2]), elem_type or "OTHER")
            elif mode == "NSET" and set_name:
                for tok in line.replace(",", " ").split():
                    if tok.lstrip("+-").isdigit():
                        nsets[set_name].append(int(tok))
            elif mode == "BOUNDARY":
                name = line.split(",")[0].strip()
                if name and not name.lstrip("+-").isdigit():
                    bc_sets.append(name)
    return {"coords": coords, "elems": elems, "nsets": nsets, "bc_sets": bc_sets}


def unconstrained_components(mesh: dict) -> list[list[int]]:
    bc = set()
    for name in mesh["bc_sets"]:
        bc.update(mesh["nsets"].get(name, []))
    adj: dict[int, set[int]] = defaultdict(set)
    for n1, n2, _typ in mesh["elems"].values():
        adj[n1].add(n2)
        adj[n2].add(n1)
    seen: set[int] = set()
    comps: list[list[int]] = []
    for n in adj:
        if n in seen:
            continue
        stack = [n]
        seen.add(n)
        cur: list[int] = []
        while stack:
            u = stack.pop()
            cur.append(u)
            for v in adj[u]:
                if v not in seen:
                    seen.add(v)
                    stack.append(v)
        comps.append(cur)
    return [c for c in comps if not any(i in bc for i in c)]


def describe_unc(mesh: dict, unc: list[list[int]]) -> list[dict]:
    coords = mesh["coords"]
    elems = mesh["elems"]
    recs = []
    for c in sorted(unc, key=lambda x: min(coords[j][0] for j in x)):
        xs = [coords[j][0] for j in c]
        eids = [eid for eid, (n1, n2, typ) in elems.items() if n1 in c and n2 in c]
        types = sorted({elems[eid][2] for eid in eids})
        recs.append(
            {
                "n": len(c),
                "nodes": sorted(c),
                "x_min": min(xs),
                "x_max": max(xs),
                "eids": eids,
                "types": types,
            }
        )
    return recs


def emit_cleared(source: Path, dest: Path) -> dict:
    source = Path(source)
    dest = Path(dest)
    frozen = ROOT / "artifacts" / "zjg_catwalk_coarsened.inp"
    site41 = ROOT / "artifacts" / "zjg_catwalk_ccx221.inp"
    site_c635 = ROOT / "artifacts" / SITE_C635_NAME
    before = {
        "82548e6a": sha256_file(frozen),
        "41fb3222": sha256_file(site41),
        "c635dad7": sha256_file(site_c635),
    }
    if before["82548e6a"] != FROZEN_SHA256:
        raise SystemExit("REFUSING: 82548e6a changed")
    if before["41fb3222"] != SITE_41FB_SHA256:
        raise SystemExit("REFUSING: 41fb3222 changed")
    if before["c635dad7"] != SITE_C635_SHA256:
        raise SystemExit("REFUSING: c635dad7 fail site changed")
    if dest.resolve() in {frozen.resolve(), site41.resolve(), site_c635.resolve()}:
        raise SystemExit(f"REFUSING: dest {dest} overwrites a frozen site")
    if sha256_file(source) != SITE_C635_SHA256:
        raise SystemExit("REFUSING: source is not c635dad7 fail site")

    mesh = parse_mesh(source)
    unc = unconstrained_components(mesh)
    desc = describe_unc(mesh, unc)
    nodes = sorted({n for c in unc for n in c})
    if len(unc) != 4 or len(nodes) != 12:
        raise SystemExit(f"REFUSING: expected 4 comps / 12 nodes, got {len(unc)} / {len(nodes)}")
    if nodes != GIVEN_FOUR["nodes"]:
        raise SystemExit(f"REFUSING: node list != given four-B31 set: {nodes}")

    text = source.read_text(encoding="utf-8")
    heading_extra = (
        "** frozen c635dad7 is the 4-unconstrained-B31 fail site and is not rewritten\n"
        "** clear four leftover unconstrained COMPONENTS (12 B31 nodes at x≈656 and 2965–2968)\n"
        f"** {CLEAR_NSET}: 9518 9519 9520 9521 33168–33175; pin UX,UY,UZ; not a calculation\n"
    )
    text = text.replace(
        "** leftover unconstrained COMPONENTS after T3D2-yarn / B31-pair consume -> N_ORPHAN_UNCONSTRAINED\n",
        "** leftover unconstrained COMPONENTS after T3D2-yarn / B31-pair consume -> N_ORPHAN_UNCONSTRAINED\n"
        + heading_extra,
    )
    nset_lines = [
        f"** c635dad7 leftover: 4 unconstrained COMPONENTS, 12 B31 nodes (not unconstrained-node count 21426)",
        f"*NSET, NSET={CLEAR_NSET}",
        "9518, 9519, 9520, 9521, 33168, 33169, 33170, 33171, 33172, 33173",
        "33174, 33175",
        "** pin the four leftover B31 fragments; does not rewrite c635dad7 / 41fb3222 / 82548e6a",
        "*BOUNDARY",
        f"{CLEAR_NSET}, 1, 3",
        "",
    ]
    marker = "*INITIAL CONDITIONS, TYPE=STRESS"
    if marker not in text:
        raise SystemExit("REFUSING: no IC keyword")
    text = text.replace(marker, "\n".join(nset_lines) + marker, 1)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(text, encoding="utf-8")

    after = {
        "82548e6a": sha256_file(frozen),
        "41fb3222": sha256_file(site41),
        "c635dad7": sha256_file(site_c635),
        "cleared": sha256_file(dest),
    }
    if after["82548e6a"] != FROZEN_SHA256 or after["41fb3222"] != SITE_41FB_SHA256:
        dest.unlink(missing_ok=True)
        raise SystemExit("REFUSING: frozen site mutated during emit")
    if after["c635dad7"] != SITE_C635_SHA256:
        dest.unlink(missing_ok=True)
        raise SystemExit("REFUSING: c635dad7 mutated during emit")
    if after["cleared"] in {FROZEN_SHA256, SITE_41FB_SHA256, SITE_C635_SHA256}:
        dest.unlink(missing_ok=True)
        raise SystemExit("REFUSING: new hash collides with a frozen site")
    if after["cleared"] != CLEARED_SHA256 or dest.stat().st_size != CLEARED_BYTES:
        dest.unlink(missing_ok=True)
        raise SystemExit(
            f"REFUSING: cleared hash/bytes drifted "
            f"(got {after['cleared']} {dest.stat().st_size})"
        )

    mesh2 = parse_mesh(dest)
    unc2 = unconstrained_components(mesh2)
    sidecar = dest.with_suffix(dest.suffix + ".sha256")
    sidecar.write_text(f"{after['cleared']}  {dest.name}\n")
    rec = {
        "source": str(source),
        "source_sha256": SITE_C635_SHA256,
        "dest": str(dest),
        "dest_sha256": after["cleared"],
        "dest_bytes": dest.stat().st_size,
        "sidecar": str(sidecar),
        "nset": CLEAR_NSET,
        "cleared_nodes": nodes,
        "before_unc": desc,
        "after_n_unconstrained_components": len(unc2),
        "after_unc": describe_unc(mesh2, unc2),
        "frozen_untouched": {
            "82548e6a": after["82548e6a"] == FROZEN_SHA256,
            "41fb3222": after["41fb3222"] == SITE_41FB_SHA256,
            "c635dad7": after["c635dad7"] == SITE_C635_SHA256,
        },
        "ccx_ran": False,
        "pushed": False,
        "merged": False,
    }
    return rec


if __name__ == "__main__":
    src = ROOT / "artifacts" / SITE_C635_NAME
    dest = ROOT / "artifacts" / CLEARED_NAME
    rec = emit_cleared(src, dest)
    eval_dir = ROOT / "eval"
    eval_dir.mkdir(exist_ok=True)
    (eval_dir / "CLEAR_FOUR_B31.json").write_text(json.dumps(rec, indent=2) + "\n")
    print(json.dumps({
        "dest_sha256": rec["dest_sha256"],
        "dest_bytes": rec["dest_bytes"],
        "after_n_unconstrained_components": rec["after_n_unconstrained_components"],
        "frozen_untouched": rec["frozen_untouched"],
        "ccx_ran": False,
    }, indent=2))
