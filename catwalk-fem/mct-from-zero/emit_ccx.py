"""Emit a CalculiX static deck migrated from the MCT body.

Geometry, sections, prestress, supports, self-weight and 二期 come from the
``.mct``. This is not a homemade STEP mesh.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

T3D2_INTPTS = (1, 2, 3, 4, 5, 6, 7, 8)
IC_FORMAT_NAME = "ccx_2.21_s7.76_element_ip_six_pk2_global"
KN_TO_N = 1000.0


def uniaxial_pk2_global(dx: float, dy: float, dz: float, sigma: float) -> tuple[float, ...]:
    length = (dx * dx + dy * dy + dz * dz) ** 0.5
    if length <= 0.0:
        raise ValueError("zero-length element")
    nx, ny, nz = dx / length, dy / length, dz / length
    return (
        sigma * nx * nx,
        sigma * ny * ny,
        sigma * nz * nz,
        sigma * nx * ny,
        sigma * nx * nz,
        sigma * ny * nz,
    )


def _dof_flags(code: str) -> list[int]:
    """MIDAS 111000 = UX UY UZ. Returns 1-based CalculiX DOF indices."""
    flags = []
    for i, ch in enumerate(code.strip()[:6], start=1):
        if ch == "1":
            flags.append(i)
    return flags


def _axial_kN_for_elem(model: dict[str, Any], eid: int) -> tuple[float | None, str]:
    ini_e = model["ini_eforce"].get(eid)
    if ini_e is not None:
        return float(ini_e["axial_mean_kN"]), "INI-EFORCE mean(i,j)"
    ini = model["iniforce"].get(eid)
    if ini is not None:
        return float(ini["axial_kN"]), "INIFORCE AXIAL"
    return None, "no MCT prestress row"


def emit_ccx(model: dict[str, Any], out_path: Path) -> dict[str, Any]:
    nodes = model["nodes"]
    elems = model["elems"]
    sections = model["sections"]
    materials = model["materials"]
    src = model["source"]

    lines: list[str] = []
    lines.append("*HEADING")
    lines.append("MCT from-zero static migrate: 猫道 - 门架索合建模型2.mct")
    lines.append(f"source sha256={src['sha256']} bytes={src['bytes']}")
    lines.append("units: CalculiX N, mm; MCT was KN, MM. Not homemade STEP.")
    lines.append(f"IC format {IC_FORMAT_NAME}. P0: statics / cable force / prestress.")
    lines.append("*NODE")
    for nid in sorted(nodes):
        n = nodes[nid]
        lines.append(f"{nid}, {n['x']:.8g}, {n['y']:.8g}, {n['z']:.8g}")

    by_sec: dict[int, list[int]] = {}
    for eid, el in elems.items():
        by_sec.setdefault(el["sec"], []).append(eid)

    lines.append("*ELEMENT, TYPE=T3D2, ELSET=E_ALL")
    for eid in sorted(elems):
        el = elems[eid]
        lines.append(f"{eid}, {el['n1']}, {el['n2']}")

    for sid, eids in sorted(by_sec.items()):
        lines.append(f"*ELSET, ELSET=E_SEC{sid}")
        chunk: list[str] = []
        for eid in sorted(eids):
            chunk.append(str(eid))
            if len(chunk) == 16:
                lines.append(", ".join(chunk) + ",")
                chunk = []
        if chunk:
            lines.append(", ".join(chunk))

    # Materials: MCT E is kN/mm^2 → N/mm^2; DEN is specific weight kN/mm^3
    # ρ_tonne/mm^3 = (DEN_kN/mm^3 * 1e12 N/m^3) / g / 1e12  → DEN * 1e3 / g_m
    # γ = DEN kN/mm^3 = DEN * 1e12 kN/m^3? No: 1 mm^3 = 1e-9 m^3 → DEN/1e-9 kN/m^3 = DEN*1e9 kN/m^3
    # Wait: DEN=1.24031e-07 kN/mm^3 = 1.24031e-07 * 1e12 N / 1e-9 m^3 / 1000? 
    # 1 kN/mm^3 = 1e3 N / 1e-9 m^3 = 1e12 N/m^3
    # DEN kN/mm^3 → DEN * 1e12 N/m^3
    # ρ = γ/g = DEN*1e12 / 9.806 m/s^2 kg/m^3
    # tonne/mm^3 = kg/m^3 * 1e-12
    # ρ_ccx = DEN * 1e12 / g / 1e12 = DEN / g
    # g from STRUCTYPE is 9806 mm/s^2 = 9.806 m/s^2
    grav = float(model["source"]["gravity_STRUCTYPE"] or 9806.0)
    g_m = grav / 1000.0  # 9806 mm/s^2 → 9.806 m/s^2
    mat_meta = {}
    for mid, mat in sorted(materials.items()):
        e_n_mm2 = None if mat["E_kN_per_mm2"] is None else mat["E_kN_per_mm2"] * KN_TO_N
        den = mat["den_raw"]
        rho = None if den is None else (den / g_m if g_m else None)
        mat_meta[mid] = {
            "name": mat["name"],
            "E_N_per_mm2": e_n_mm2,
            "nu": mat["nu"],
            "den_raw_kN_per_mm3": den,
            "rho_tonne_per_mm3": rho,
            "rho_formula": "DEN_kN/mm3 / (GRAV_mm/s2 / 1000) = tonne/mm3 under N-mm-s",
        }
        lines.append(f"*MATERIAL, NAME=MAT{mid}")
        lines.append("*ELASTIC")
        lines.append(f"{e_n_mm2:.8g}, {mat['nu']}")
        if rho is not None:
            lines.append("*DENSITY")
            lines.append(f"{rho:.8e}")

    sec_used = {}
    for sid, sec in sorted(sections.items()):
        area = sec["area_mm2"]
        if area is None:
            raise ValueError(f"section {sid} has no area; refuse to invent")
        mid = None
        # majority material among elems of this section
        mats = [elems[e]["mat"] for e in by_sec.get(sid, [])]
        if mats:
            mid = max(set(mats), key=mats.count)
        sec_used[sid] = {"area_mm2": area, "mat": mid, "formula": sec["area_formula"]}
        lines.append(f"*SOLID SECTION, ELSET=E_SEC{sid}, MATERIAL=MAT{mid}")
        lines.append(f"{area:.8g}")

    ic_eids = []
    ic_skipped = []
    lines.append(f"*INITIAL CONDITIONS, TYPE=STRESS")
    lines.append(f"** {IC_FORMAT_NAME}; sigma = F_N / A_mm2 from MCT INI-EFORCE mean, else INIFORCE")
    for eid in sorted(elems):
        el = elems[eid]
        force_kN, src_force = _axial_kN_for_elem(model, eid)
        area = sections[el["sec"]]["area_mm2"]
        if force_kN is None or area is None or area <= 0.0:
            ic_skipped.append(eid)
            continue
        n1, n2 = nodes[el["n1"]], nodes[el["n2"]]
        sigma = (force_kN * KN_TO_N) / area
        sxx, syy, szz, sxy, sxz, syz = uniaxial_pk2_global(
            n2["x"] - n1["x"], n2["y"] - n1["y"], n2["z"] - n1["z"], sigma
        )
        for ip in T3D2_INTPTS:
            lines.append(
                f"{eid}, {ip}, {sxx:.6e}, {syy:.6e}, {szz:.6e}, {sxy:.6e}, {sxz:.6e}, {syz:.6e}"
            )
        ic_eids.append({"eid": eid, "F_kN": force_kN, "A_mm2": area, "sigma_N_mm2": sigma, "from": src_force})

    lines.append("*BOUNDARY")
    n_bc = 0
    for c in model["constraints"]:
        dofs = _dof_flags(c["dof"])
        for nid in c["nodes"]:
            for d in dofs:
                lines.append(f"{nid}, {d}, {d}")
                n_bc += 1

    lines.append("*STEP")
    lines.append("*STATIC")
    sw = model["selfweight"]
    if sw is not None:
        lines.append("*DLOAD")
        lines.append(f"E_ALL, GRAV, {grav:.8g}, {sw['gx']}, {sw['gy']}, {sw['gz']}")
    if model["conload_erqi"]:
        lines.append("*CLOAD")
        n_cload = 0
        for rec in model["conload_erqi"]:
            if abs(rec["fx_kN"]) >= 1e-12:
                lines.append(f"{rec['nid']}, 1, {rec['fx_kN'] * KN_TO_N:.8g}")
                n_cload += 1
            if abs(rec["fy_kN"]) >= 1e-12:
                lines.append(f"{rec['nid']}, 2, {rec['fy_kN'] * KN_TO_N:.8g}")
                n_cload += 1
            if abs(rec["fz_kN"]) >= 1e-12:
                lines.append(f"{rec['nid']}, 3, {rec['fz_kN'] * KN_TO_N:.8g}")
                n_cload += 1
    else:
        n_cload = 0
    lines.append("*NODE FILE")
    lines.append("U")
    lines.append("*EL FILE")
    lines.append("S, E")
    lines.append("*END STEP")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    text = "\n".join(lines) + "\n"
    out_path.write_text(text, encoding="utf-8")
    return {
        "path": str(out_path),
        "bytes": len(text.encode("utf-8")),
        "n_nodes": len(nodes),
        "n_elems": len(elems),
        "n_ic_elems": len(ic_eids),
        "n_ic_rows": len(ic_eids) * len(T3D2_INTPTS),
        "n_ic_skipped_no_prestress": ic_skipped,
        "n_boundary_rows": n_bc,
        "n_cload_rows": n_cload,
        "ic_format": IC_FORMAT_NAME,
        "materials_converted": mat_meta,
        "sections_used": sec_used,
        "source_sha256": src["sha256"],
        "homemade_step": False,
        "from_mct_body": True,
    }
