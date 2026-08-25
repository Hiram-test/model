"""Build MCT from-zero sidecar + inp. Does not push. Does not rewrite 760c0ee4."""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))

from emit_ccx import emit_ccx  # noqa: E402
from parse_mct import sidecar_from_model, load_mct  # noqa: E402

ART = HERE / "artifacts"
EVAL = ROOT / "eval"


def _dump(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def archive_index_from_package_members(csv_path: Path) -> dict:
    """Index only. These CSVs are not the new main."""
    needle = "03_猫道动力分析\\MCT基准复现_V1.0\\"
    rows = []
    text = csv_path.read_text(encoding="utf-8-sig")
    for line in text.splitlines()[1:]:
        if needle not in line:
            continue
        # "archive-0004.tar.zst","TAR","03_...\\file","0","bytes","sha"
        parts = [p.strip().strip('"') for p in line.split('","')]
        if len(parts) < 6:
            continue
        rel = parts[2].replace("\\", "/")
        rows.append(
            {
                "shard": parts[0].strip('"'),
                "relative": rel,
                "bytes": int(parts[4]),
                "sha256": parts[5].strip().strip('"'),
            }
        )
    return {
        "kind": "archive_index_only",
        "directory": "03_猫道动力分析/MCT基准复现_V1.0/",
        "used_as_new_main": False,
        "note": "Sibling archive of a prior MCT baseline dump. From-zero source is the .mct body.",
        "n_members": len(rows),
        "members": rows,
    }


def ansys_db_trace(probe_path: Path | None, db_sha_path: Path | None) -> dict:
    probe = {}
    if probe_path and probe_path.is_file():
        probe = json.loads(probe_path.read_text(encoding="utf-8"))
    db_sha = None
    db_bytes = None
    if db_sha_path and db_sha_path.is_file():
        db_sha = db_sha_path.read_text(encoding="utf-8").strip().split()[0]
        # sibling db
        db = db_sha_path.parent / "cw_S10_0716t050342_a4_eq.db"
        if db.is_file():
            db_bytes = db.stat().st_size
    return {
        "kind": "ansys_s10_db_extract_trace",
        "extracted_from_db": False,
        "reason": "No MAPDL/ANSYS on this VM. Full-file ASCII probe of the .db found 0 prestress/LINK180 keys. Numbers were not invented.",
        "db": {
            "name": "cw_S10_0716t050342_a4_eq.db",
            "release": "https://github.com/Hiram-test/model/releases/download/catwalk-attachment23-v2.0-s10-20260716/cw_S10_0716t050342_a4_eq.db",
            "expected_sha256": "17e0bac8717e7c32a407571d33e38dd777736b31b6656684e53449fa8c9d40fd",
            "expected_bytes": 700186624,
            "observed_sha256": db_sha,
            "observed_bytes": db_bytes,
            "sha256_match": db_sha == "17e0bac8717e7c32a407571d33e38dd777736b31b6656684e53449fa8c9d40fd",
        },
        "string_probe": probe,
        "mapdl_present": False,
    }


def mct_vs_ansys(sidecar: dict, db_trace: dict) -> dict:
    named = sidecar.get("named_cables", {})
    m728 = named.get("728", {})
    # APDL snapshot numbers are labeled NOT from .db POST1.
    return {
        "kind": "mct_vs_ansys_statics_prestress",
        "not_a_scientific_claim": True,
        "one_to_one_elem_map": False,
        "mct": {
            "source": "猫道 - 门架索合建模型2.mct body",
            "sha256": sidecar["source"]["sha256"],
            "unit": "kN, mm",
            "n_nodes": sidecar["counts"]["n_nodes"],
            "n_elems": sidecar["counts"]["n_elems"],
            "n_TENSTR": sidecar["counts"]["n_TENSTR"],
            "INIFORCE_AXIAL_kN": sidecar["prestress_stats_kN"]["INIFORCE_AXIAL"],
            "INI-EFORCE_mean_kN": sidecar["prestress_stats_kN"]["INI-EFORCE_mean"],
            "elem_728_INIFORCE_kN": m728.get("iniforce_kN"),
            "elem_728_INI-EFORCE_i_j_kN": [
                m728.get("ini_eforce_i_kN"),
                m728.get("ini_eforce_j_kN"),
            ],
            "elem_729_INIFORCE_kN": named.get("729", {}).get("iniforce_kN"),
            "note": "Y≈0 single-line 2-D equivalent. Face-layer anchors and gantry anchors are separate groups in the MCT.",
        },
        "ansys_db": {
            "extracted": False,
            "trace": db_trace["reason"],
            "db_sha256_match": db_trace["db"]["sha256_match"],
            "link180_from_db": None,
            "prestress_from_db": None,
        },
        "ansys_apdl_snapshot_not_from_db": {
            "labeled": True,
            "source": "archive APDL of official run S10_SECTION_SHEAR_20260716T050342389124Z + LS2 oracle CSV. Not .db POST1.",
            "n_LINK180_oracle": 73692,
            "oracle_min_N": 519002.6875,
            "oracle_max_N": 1573314.125,
            "oracle_max_elem": 400003,
            "downpull_apdl_comment": "MCT elements 728/729: north/south main-tower catwalk downpull equivalents. Each MCT 2-D equivalent is duplicated to the two physical catwalks.",
            "downpull_apdl_area_mm2": 22298.691649500659,
            "mct_section1_area_mm2": (sidecar["sections"].get(1) or sidecar["sections"].get("1") or {}).get("area_mm2"),
        },
        "compare_notes": [
            "Different meshes: MCT 1194 elems vs S10 73692 LINK180. No 1:1 map.",
            "MCT 728 INIFORCE is in kN from the .mct. S10 oracle max is N on LINK180 400003 from APDL/oracle, not from the .db.",
            "Do not treat APDL/oracle numbers as extracted from cw_S10_0716t050342_a4_eq.db.",
        ],
    }


def main() -> int:
    model = load_mct()
    sidecar = sidecar_from_model(model)
    ART.mkdir(parents=True, exist_ok=True)
    EVAL.mkdir(parents=True, exist_ok=True)
    _dump(ART / "mct_from_zero_sidecar.json", sidecar)
    meta = emit_ccx(model, ART / "mct_from_zero_static.ccx.inp")
    _dump(ART / "mct_from_zero_inp_meta.json", meta)

    members = Path("/tmp/mct-src/manifest/package-members.csv")
    if members.is_file():
        _dump(ART / "archive_index_MCT基准复现_V1.0.json", archive_index_from_package_members(members))

    db_trace = ansys_db_trace(
        Path("/tmp/s10-db-reread/string_probe.json"),
        Path("/tmp/s10-db-reread/SHA256.txt"),
    )
    _dump(ART / "ansys_db_extract_trace.json", db_trace)
    _dump(ART / "mct_vs_ansys.json", mct_vs_ansys(sidecar, db_trace))
    _dump(EVAL / "MCT_FROM_ZERO.json", sidecar)
    _dump(EVAL / "ANSYS_DB_EXTRACT_TRACE.json", db_trace)
    print(json.dumps({"sidecar": str(ART / "mct_from_zero_sidecar.json"), "inp": meta}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
