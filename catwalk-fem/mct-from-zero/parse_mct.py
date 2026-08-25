"""From-zero parser for the MIDAS Civil NX MCT.

Reads the ``.mct`` body only. Archive CSV under
``03_猫道动力分析/MCT基准复现_V1.0/`` is an index sibling, not the source.
"""

from __future__ import annotations

import hashlib
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any

EXPECTED_SHA256 = "0d18e3f7b009e0306fb4b9f3051b4a16d05fa24d9e966774e809b8942a4f22e1"
EXPECTED_BYTES = 448673
SOURCE_RELATIVE = "01_设计资料与规范/猫道 - 门架索合建模型2.mct"
DEFAULT_SOURCE = Path(__file__).resolve().parent / "source" / SOURCE_RELATIVE

_RANGE = re.compile(r"^(\d+)to(\d+)(?:by(\d+))?$", re.IGNORECASE)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def expand_midas_list(spec: str) -> list[int]:
    """Expand a MIDAS element/node list: ``4``, ``1086 1259``, ``447to449``, ``180to243by21``."""
    ids: list[int] = []
    for tok in spec.replace(",", " ").split():
        tok = tok.strip()
        if not tok:
            continue
        m = _RANGE.fullmatch(tok)
        if m:
            start, end = int(m.group(1)), int(m.group(2))
            step = int(m.group(3) or 1)
            if step <= 0:
                raise ValueError(f"invalid MIDAS step in {tok!r}")
            ids.extend(range(start, end + 1, step))
        else:
            ids.append(int(tok))
    return ids


def _join_continuations(text: str) -> list[tuple[int, str]]:
    raw = text.splitlines()
    out: list[tuple[int, str]] = []
    i = 0
    while i < len(raw):
        line = raw[i]
        start = i + 1
        while line.rstrip().endswith("\\"):
            i += 1
            if i >= len(raw):
                break
            line = line.rstrip()[:-1] + " " + raw[i].lstrip()
        out.append((start, line))
        i += 1
    return out


def _is_star_command(line: str) -> bool:
    s = line.lstrip()
    return s.startswith("*") and not s.startswith("*;")


def _command_name(line: str) -> str:
    head = line.lstrip().split(";", 1)[0].strip()
    return head.split(",", 1)[0].strip()


def _data_rows(joined: list[tuple[int, str]], start_idx: int) -> tuple[list[tuple[int, str]], int]:
    rows: list[tuple[int, str]] = []
    i = start_idx + 1
    while i < len(joined):
        _ln, line = joined[i]
        if _is_star_command(line):
            break
        rows.append(joined[i])
        i += 1
    return rows, i


def _non_comment_rows(rows: list[tuple[int, str]]) -> list[tuple[int, str]]:
    out = []
    for ln, line in rows:
        s = line.strip()
        if not s or s.startswith(";"):
            continue
        out.append((ln, line))
    return out


def _split_csv(line: str) -> list[str]:
    return [p.strip() for p in line.split(",")]


def _stats(values: list[float]) -> dict[str, float | int]:
    if not values:
        return {"n": 0}
    return {
        "n": len(values),
        "min": min(values),
        "max": max(values),
        "sum": float(sum(values)),
        "mean": float(sum(values) / len(values)),
    }


def _section_area_mm2(sec: dict[str, Any]) -> tuple[float | None, str]:
    """Area from MCT *SECTION fields. UNIT is KN, MM. Do not invent extra factors."""
    shape = str(sec.get("shape") or "").upper()
    data = sec.get("data") or []
    if shape == "SR" and len(data) >= 1:
        diameter = float(data[0])
        area = math.pi * (diameter * 0.5) ** 2
        return area, f"SR solid round A=pi*(D/2)^2 with D={diameter} mm from *SECTION"
    if shape == "B" and len(data) >= 4:
        b, h, tw, tf = (float(data[0]), float(data[1]), float(data[2]), float(data[3]))
        inner_b = b - 2.0 * tw
        inner_h = h - 2.0 * tf
        one = b * h - max(inner_b, 0.0) * max(inner_h, 0.0)
        name = str(sec.get("name") or "")
        n_bar = 2.0 if "2根" in name else 1.0
        return one * n_bar, (
            f"B box A=n*(B*H-(B-2tw)*(H-2tf)) B={b} H={h} tw={tw} tf={tf} n={n_bar} "
            f"from *SECTION name={name!r}"
        )
    return None, "no area formula applied; raw *SECTION fields only"


def parse_mct_text(text: str, *, sha256: str, nbytes: int, source_path: str) -> dict[str, Any]:
    joined = _join_continuations(text)
    blocks: dict[str, list[tuple[int, str]]] = {}
    block_starts: dict[str, int] = {}
    i = 0
    while i < len(joined):
        ln, line = joined[i]
        if _is_star_command(line):
            cmd = _command_name(line)
            rows, nxt = _data_rows(joined, i)
            # First occurrence of a command name; later *USE-STLD / *CONLOAD pairs kept as list
            key = cmd
            if cmd in {"*USE-STLD", "*CONLOAD", "*SYSTEMPER"}:
                key = f"{cmd}@{ln}"
            blocks[key] = rows
            block_starts[key] = ln
            i = nxt
            continue
        i += 1

    unit_rows = _non_comment_rows(blocks.get("*UNIT", []))
    unit_force, unit_len = "KN", "MM"
    if unit_rows:
        parts = _split_csv(unit_rows[0][1])
        unit_force = parts[0].upper()
        unit_len = parts[1].upper() if len(parts) > 1 else "MM"

    version = None
    if blocks.get("*VERSION"):
        vr = _non_comment_rows(blocks["*VERSION"])
        if vr:
            version = vr[0][1].strip()

    grav = None
    st = _non_comment_rows(blocks.get("*STRUCTYPE", []))
    if st:
        parts = _split_csv(st[0][1])
        if len(parts) >= 6:
            grav = float(parts[5])

    nodes: dict[int, dict[str, Any]] = {}
    for ln, line in _non_comment_rows(blocks.get("*NODE", [])):
        parts = _split_csv(line)
        nid = int(parts[0])
        nodes[nid] = {
            "id": nid,
            "x": float(parts[1]),
            "y": float(parts[2]),
            "z": float(parts[3]),
            "line": ln,
        }

    elems: dict[int, dict[str, Any]] = {}
    for ln, line in _non_comment_rows(blocks.get("*ELEMENT", [])):
        parts = _split_csv(line)
        eid = int(parts[0])
        elems[eid] = {
            "id": eid,
            "type": parts[1],
            "mat": int(parts[2]),
            "sec": int(parts[3]),
            "n1": int(parts[4]),
            "n2": int(parts[5]),
            "line": ln,
        }

    materials: dict[int, dict[str, Any]] = {}
    for ln, line in _non_comment_rows(blocks.get("*MATERIAL", [])):
        parts = _split_csv(line)
        mid = int(parts[0])
        # USER/STEEL line: iMAT, TYPE, MNAME, ..., 2, E, nu, thermal, den, mass
        e_val = None
        nu = None
        den = None
        if len(parts) >= 14:
            try:
                e_val = float(parts[10])
                nu = float(parts[11])
                den = float(parts[13])
            except ValueError:
                pass
        materials[mid] = {
            "id": mid,
            "type": parts[1] if len(parts) > 1 else "",
            "name": parts[2] if len(parts) > 2 else "",
            "E_kN_per_mm2": e_val,
            "nu": nu,
            "den_raw": den,
            "line": ln,
            "raw": line.strip(),
        }

    sections: dict[int, dict[str, Any]] = {}
    for ln, line in _non_comment_rows(blocks.get("*SECTION", [])):
        parts = _split_csv(line)
        sid = int(parts[0])
        name = parts[2] if len(parts) > 2 else ""
        shape = ""
        data: list[float] = []
        # SHAPE token is the first of SR/B/... after YES, NO
        for i_p, tok in enumerate(parts):
            if tok.upper() in {"SR", "B", "P", "SB", "T", "C", "H"}:
                shape = tok.upper()
                rest = parts[i_p + 1 :]
                # skip optional integer type code then numeric dims
                nums: list[float] = []
                for r in rest:
                    try:
                        nums.append(float(r))
                    except ValueError:
                        if nums:
                            break
                if nums and float(nums[0]).is_integer() and len(nums) > 1:
                    data = nums[1:]
                else:
                    data = nums
                break
        area, area_note = _section_area_mm2({"shape": shape, "data": data, "name": name})
        sections[sid] = {
            "id": sid,
            "name": name,
            "shape": shape,
            "data": data,
            "area_mm2": area,
            "area_formula": area_note,
            "line": ln,
            "raw": line.strip(),
        }

    iniforce: dict[int, dict[str, Any]] = {}
    iniforce_dup: list[int] = []
    iniforce_rows = 0
    for ln, line in _non_comment_rows(blocks.get("*INIFORCE", [])):
        parts = _split_csv(line)
        if len(parts) < 3:
            continue
        force = float(parts[-1])
        direction = parts[-2].upper()
        eids = expand_midas_list(",".join(parts[:-2]))
        iniforce_rows += 1
        for eid in eids:
            if eid in iniforce:
                iniforce_dup.append(eid)
            iniforce[eid] = {
                "eid": eid,
                "dir": direction,
                "axial_kN": force,
                "line": ln,
            }

    ini_eforce: dict[int, dict[str, Any]] = {}
    for ln, line in _non_comment_rows(blocks.get("*INI-EFORCE", [])):
        parts = _split_csv(line)
        # TRUSS, ID, Axial-i, Axial-j
        if len(parts) < 4:
            continue
        eid = int(parts[1])
        fi = float(parts[2])
        fj = float(parts[3])
        ini_eforce[eid] = {
            "eid": eid,
            "type": parts[0],
            "axial_i_kN": fi,
            "axial_j_kN": fj,
            "axial_mean_kN": 0.5 * (fi + fj),
            "line": ln,
        }

    equi_mforce: dict[int, dict[str, Any]] = {}
    for ln, line in _non_comment_rows(blocks.get("*EQUI-MFORCE", [])):
        parts = _split_csv(line)
        if len(parts) < 4:
            continue
        eid = int(parts[1])
        equi_mforce[eid] = {
            "eid": eid,
            "type": parts[0],
            "fx_i_kN": float(parts[2]),
            "fx_j_kN": float(parts[3]),
            "line": ln,
        }

    constraints: list[dict[str, Any]] = []
    for ln, line in _non_comment_rows(blocks.get("*CONSTRAINT", [])):
        parts = _split_csv(line)
        if len(parts) < 2:
            continue
        nids = expand_midas_list(parts[0])
        dof = parts[1]
        name = parts[2] if len(parts) > 2 else ""
        constraints.append({"nodes": nids, "dof": dof, "name": name, "line": ln})

    groups: dict[str, dict[str, Any]] = {}
    for ln, line in _non_comment_rows(blocks.get("*GROUP", [])):
        parts = _split_csv(line)
        if not parts:
            continue
        gname = parts[0]
        node_spec = parts[1] if len(parts) > 1 else ""
        elem_spec = parts[2] if len(parts) > 2 else ""
        groups[gname] = {
            "name": gname,
            "nodes": expand_midas_list(node_spec) if node_spec else [],
            "elems": expand_midas_list(elem_spec) if elem_spec else [],
            "line": ln,
        }

    selfweight = None
    for ln, line in _non_comment_rows(blocks.get("*SELFWEIGHT", [])):
        parts = _split_csv(line)
        selfweight = {
            "gx": float(parts[0]),
            "gy": float(parts[1]),
            "gz": float(parts[2]),
            "group": parts[3] if len(parts) > 3 else "",
            "line": ln,
        }
        break

    conload_erqi: list[dict[str, Any]] = []
    for key, rows in blocks.items():
        if not key.startswith("*CONLOAD@"):
            continue
        for ln, line in _non_comment_rows(rows):
            parts = _split_csv(line)
            if len(parts) < 4:
                continue
            case = parts[7] if len(parts) > 7 else ""
            rec = {
                "nid": int(parts[0]),
                "fx_kN": float(parts[1]),
                "fy_kN": float(parts[2]),
                "fz_kN": float(parts[3]),
                "case": case,
                "line": ln,
            }
            if case == "二期":
                conload_erqi.append(rec)

    # Internal MCT consistency: INIFORCE vs mean(INI-EFORCE) where both exist.
    both = sorted(set(iniforce) & set(ini_eforce))
    rel = []
    for eid in both:
        a = iniforce[eid]["axial_kN"]
        b = ini_eforce[eid]["axial_mean_kN"]
        if b != 0.0:
            rel.append(abs(a - b) / abs(b))
    consistency = {
        "n_both": len(both),
        "n_iniforce_only": len(set(iniforce) - set(ini_eforce)),
        "n_ini_eforce_only": len(set(ini_eforce) - set(iniforce)),
        "abs_rel_iniforce_vs_ini_eforce_mean": _stats(rel) if rel else {"n": 0},
        "note": "Both columns are from the same .mct. INIFORCE is geometric-stiffness axial; INI-EFORCE is i/j element axial.",
    }

    tenstr_ids = [e for e, v in elems.items() if v["type"] == "TENSTR"]
    truss_ids = [e for e, v in elems.items() if v["type"] == "TRUSS"]
    named = {}
    for eid in (728, 729, 1, 2, 4):
        if eid in iniforce or eid in ini_eforce or eid in elems:
            named[str(eid)] = {
                "elem": elems.get(eid),
                "iniforce_kN": iniforce[eid]["axial_kN"] if eid in iniforce else None,
                "iniforce_line": iniforce[eid]["line"] if eid in iniforce else None,
                "ini_eforce_i_kN": ini_eforce[eid]["axial_i_kN"] if eid in ini_eforce else None,
                "ini_eforce_j_kN": ini_eforce[eid]["axial_j_kN"] if eid in ini_eforce else None,
                "ini_eforce_line": ini_eforce[eid]["line"] if eid in ini_eforce else None,
            }

    ys = [n["y"] for n in nodes.values()]
    xs = [n["x"] for n in nodes.values()]
    zs = [n["z"] for n in nodes.values()]

    model = {
        "source": {
            "path": source_path,
            "relative": SOURCE_RELATIVE,
            "bytes": nbytes,
            "sha256": sha256,
            "expected_sha256": EXPECTED_SHA256,
            "sha256_match": sha256 == EXPECTED_SHA256 and nbytes == EXPECTED_BYTES,
            "encoding": "GB18030",
            "product": "MIDAS Civil NX MCT",
            "version": version,
            "unit_force": unit_force,
            "unit_length": unit_len,
            "gravity_STRUCTYPE": grav,
            "new_main": False,
            "from_zero": True,
            "used_archive_csv_as_source": False,
        },
        "counts": {
            "n_nodes": len(nodes),
            "n_elems": len(elems),
            "n_TENSTR": len(tenstr_ids),
            "n_TRUSS": len(truss_ids),
            "elem_types": dict(Counter(v["type"] for v in elems.values())),
            "elem_mats": {str(k): v for k, v in Counter(e["mat"] for e in elems.values()).items()},
            "elem_secs": {str(k): v for k, v in Counter(e["sec"] for e in elems.values()).items()},
            "n_iniforce_rows": iniforce_rows,
            "n_iniforce_eids": len(iniforce),
            "n_iniforce_duplicate_eids": len(iniforce_dup),
            "n_ini_eforce": len(ini_eforce),
            "n_equi_mforce": len(equi_mforce),
            "n_conload_erqi": len(conload_erqi),
            "n_groups": len(groups),
        },
        "bbox_mm": {
            "x_min": min(xs) if xs else None,
            "x_max": max(xs) if xs else None,
            "y_min": min(ys) if ys else None,
            "y_max": max(ys) if ys else None,
            "z_min": min(zs) if zs else None,
            "z_max": max(zs) if zs else None,
            "note": "MCT Y is numerically ~0 (single-line 2-D equivalent). Not the dual-walkway S10 mesh.",
        },
        "materials": materials,
        "sections": sections,
        "nodes": nodes,
        "elems": elems,
        "iniforce": iniforce,
        "ini_eforce": ini_eforce,
        "equi_mforce": equi_mforce,
        "constraints": constraints,
        "groups": groups,
        "selfweight": selfweight,
        "conload_erqi": conload_erqi,
        "prestress_stats_kN": {
            "INIFORCE_AXIAL": _stats([v["axial_kN"] for v in iniforce.values()]),
            "INI-EFORCE_mean": _stats([v["axial_mean_kN"] for v in ini_eforce.values()]),
            "INI-EFORCE_i": _stats([v["axial_i_kN"] for v in ini_eforce.values()]),
            "INI-EFORCE_j": _stats([v["axial_j_kN"] for v in ini_eforce.values()]),
        },
        "mct_internal_force_consistency": consistency,
        "named_cables": named,
        "group_counts": {
            name: {"n_nodes": len(g["nodes"]), "n_elems": len(g["elems"])}
            for name, g in groups.items()
        },
    }
    return model


def load_mct(path: Path | None = None) -> dict[str, Any]:
    src = Path(path) if path is not None else DEFAULT_SOURCE
    raw = src.read_bytes()
    digest = sha256_bytes(raw)
    if digest != EXPECTED_SHA256 or len(raw) != EXPECTED_BYTES:
        raise ValueError(
            f"MCT hash/size mismatch: got {digest} {len(raw)} B; "
            f"expected {EXPECTED_SHA256} {EXPECTED_BYTES} B"
        )
    text = raw.decode("gb18030")
    repo = Path(__file__).resolve().parents[2]
    try:
        shown = str(src.resolve().relative_to(repo))
    except ValueError:
        shown = SOURCE_RELATIVE
    return parse_mct_text(text, sha256=digest, nbytes=len(raw), source_path=shown)


def sidecar_from_model(model: dict[str, Any]) -> dict[str, Any]:
    """JSON-safe sidecar: counts, prestress, named cables. Not a scientific claim."""
    src = model["source"]
    return {
        "kind": "mct_from_zero_sidecar",
        "not_a_scientific_claim": True,
        "used_archive_csv_as_new_main": False,
        "source": src,
        "counts": model["counts"],
        "bbox_mm": model["bbox_mm"],
        "materials": model["materials"],
        "sections": model["sections"],
        "prestress_stats_kN": model["prestress_stats_kN"],
        "mct_internal_force_consistency": model["mct_internal_force_consistency"],
        "named_cables": model["named_cables"],
        "group_counts": model["group_counts"],
        "constraints": model["constraints"],
        "selfweight": model["selfweight"],
        "conload_erqi_stats_kN": {
            "n": len(model["conload_erqi"]),
            "n_nonzero_fz": sum(1 for r in model["conload_erqi"] if abs(r["fz_kN"]) >= 1e-4),
            "fz": _stats([r["fz_kN"] for r in model["conload_erqi"]]),
        },
        "tenstr_without_iniforce": sorted(
            e
            for e, v in model["elems"].items()
            if v["type"] == "TENSTR" and e not in model["iniforce"]
        ),
        "tenstr_without_ini_eforce": sorted(
            e
            for e, v in model["elems"].items()
            if v["type"] == "TENSTR" and e not in model["ini_eforce"]
        ),
    }
