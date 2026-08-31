"""From-zero MCT parse and migrate. Does not touch 760c0ee4."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "mct-from-zero"))

from parse_mct import (  # noqa: E402
    EXPECTED_BYTES,
    EXPECTED_SHA256,
    SOURCE_RELATIVE,
    expand_midas_list,
    load_mct,
    sidecar_from_model,
)
from emit_ccx import emit_ccx  # noqa: E402

SOURCE = ROOT / "mct-from-zero" / "source" / SOURCE_RELATIVE
FROZEN = ROOT / "artifacts" / "zjg_catwalk_cleared.inp"
FROZEN_SHA = "760c0ee44d7077ddfb84273cba916abb1fea1eb2a0ff6cfe57abaec9b0585de9"


def test_source_is_chinese_path_not_unicode_escape():
    assert SOURCE.name == "猫道 - 门架索合建模型2.mct"
    assert SOURCE.parent.name == "01_设计资料与规范"
    assert "\\u" not in str(SOURCE)
    raw = SOURCE.read_bytes()
    assert len(raw) == EXPECTED_BYTES
    assert hashlib.sha256(raw).hexdigest() == EXPECTED_SHA256


def test_expand_midas_list():
    assert expand_midas_list("4") == [4]
    assert expand_midas_list("1086 1259") == [1086, 1259]
    assert expand_midas_list("447to449") == [447, 448, 449]
    assert expand_midas_list("1063to1065 1280to1282") == [1063, 1064, 1065, 1280, 1281, 1282]
    assert expand_midas_list("180to243by21") == [180, 201, 222, 243]


def test_from_zero_counts_and_prestress():
    model = load_mct(SOURCE)
    assert model["source"]["sha256_match"] is True
    assert model["source"]["used_archive_csv_as_source"] is False
    assert model["source"]["unit_force"] == "KN"
    assert model["source"]["unit_length"] == "MM"
    assert model["counts"]["n_nodes"] == 1125
    assert model["counts"]["n_elems"] == 1194
    assert model["counts"]["n_TENSTR"] == 1123
    assert model["counts"]["n_TRUSS"] == 71
    assert model["counts"]["n_ini_eforce"] == 1123
    assert model["counts"]["n_iniforce_eids"] >= 1123
    # prestress is in the MCT
    assert 728 in model["iniforce"]
    assert model["iniforce"][728]["axial_kN"] == 1482.74
    assert 729 in model["iniforce"]
    assert 4 in model["iniforce"]
    assert model["iniforce"][4]["axial_kN"] == 12209.3
    assert 1 in model["ini_eforce"]
    assert model["ini_eforce"][1]["axial_i_kN"] == 15649.8
    assert model["ini_eforce"][1]["axial_j_kN"] == 15722.7
    # 21 cross-passage nodes in the MCT group, not invented
    assert len(model["groups"]["横向通道节点"]["nodes"]) == 21
    # 71 gantry frame elems on the single-line MCT
    assert len(model["groups"]["门架"]["elems"]) == 71
    # every TENSTR has INI-EFORCE
    missing = [e for e, v in model["elems"].items() if v["type"] == "TENSTR" and e not in model["ini_eforce"]]
    assert missing == []


def test_emit_is_mct_migrate(tmp_path: Path):
    model = load_mct(SOURCE)
    out = tmp_path / "mct.ccx.inp"
    meta = emit_ccx(model, out)
    text = out.read_text(encoding="utf-8")
    assert meta["from_mct_body"] is True
    assert meta["homemade_step"] is False
    assert meta["n_nodes"] == 1125
    assert meta["n_elems"] == 1194
    assert meta["n_ic_elems"] == 1123
    assert "*INITIAL CONDITIONS, TYPE=STRESS" in text
    assert "*ELEMENT, TYPE=T3D2" in text
    assert "*ELEMENT, TYPE=B31" in text
    assert "*BEAM SECTION" in text
    assert "猫道 - 门架索合建模型2.mct" in text
    assert EXPECTED_SHA256 in text
    sidecar = sidecar_from_model(model)
    assert sidecar["used_archive_csv_as_new_main"] is False
    assert sidecar["not_a_scientific_claim"] is True


def test_760c0ee4_untouched():
    h = hashlib.sha256(FROZEN.read_bytes()).hexdigest()
    assert h == FROZEN_SHA


def test_sidecar_on_disk_if_built():
    p = ROOT / "mct-from-zero" / "artifacts" / "mct_from_zero_sidecar.json"
    if not p.is_file():
        return
    data = json.loads(p.read_text(encoding="utf-8"))
    assert data["source"]["sha256"] == EXPECTED_SHA256
    assert data["used_archive_csv_as_new_main"] is False


if __name__ == "__main__":
    test_source_is_chinese_path_not_unicode_escape()
    test_expand_midas_list()
    test_from_zero_counts_and_prestress()
    test_760c0ee4_untouched()
    from tempfile import TemporaryDirectory

    with TemporaryDirectory() as d:
        test_emit_is_mct_migrate(Path(d))
    test_sidecar_on_disk_if_built()
    print("ok")
