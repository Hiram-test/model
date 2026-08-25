"""Form-finding on 974211b2: lock force from MCT INIFORCE, six-case cards, DYN.

Does not rewrite the main deck. Does not import 附件2-3 表5-4 or TARGET-FREQ.
Does not write 符合附件2-3. Modeling post only — no paper manuscript.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "artifacts" / "zjg_catwalk_migrate_main.inp"
FORM = ROOT / "eval" / "formfind_974211b2"
P1 = ROOT / "eval" / "ccx_P1_nlgeom_974211b2" / "migrate_P1.inp"
DYN = ROOT / "eval" / "ccx_DYN_freq_974211b2" / "migrate_DYN.inp"
DYN_DAUGHTER = FORM / "daughters" / "migrate_DYN.inp"
LEDGER = FORM / "MODELING.md"
EVIDENCE = FORM / "EVIDENCE.json"
HASH_LEDGER = ROOT / "artifacts" / "HASH_LEDGER.json"

MAIN_SHA = "974211b2ddfe2950548ee2455bc22e1e2e68d3e1f53df4c4e1eb71ece0267fd1"
P1_SHA = "be533c5f3228aacf19aea4913b503c2c6fac6d6246f6e6ab7b1eba4720e630ae"


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def test_main_bytes_untouched():
    assert MAIN.is_file()
    assert sha256(MAIN) == MAIN_SHA
    assert MAIN.stat().st_size == 930300


def test_p1_is_nlgeom_only_plus_eight_bytes():
    assert P1.is_file()
    assert sha256(P1) == P1_SHA
    assert P1.stat().st_size == 930308
    main = MAIN.read_bytes()
    p1 = P1.read_bytes()
    assert main.count(b"*STEP\n*STATIC\n") == 1
    assert b"*STEP, NLGEOM\n*STATIC\n" in p1
    assert p1.replace(b"*STEP, NLGEOM\n*STATIC\n", b"*STEP\n*STATIC\n", 1) == main


def test_lock_force_from_mct_iniforce_not_table_5_4():
    lock = json.loads((FORM / "lock_force.json").read_text())
    assert lock["n_iniforce"] == 1123
    assert lock["n_TENSTR_lock"] == 1123
    assert lock["n_portal_truss_without_iniforce"] == 71
    assert lock["mean_kN"] == pytest.approx(7966.67, abs=0.02)
    assert lock["max_kN"] == pytest.approx(15724.3, abs=0.05)
    assert lock["eid1_sigma_equals_F_over_A"] is True
    assert lock["source"] == "MCT *INIFORCE / *INI-EFORCE"
    assert lock["not_table_5_4"] is True
    blob = json.dumps(lock, ensure_ascii=False)
    assert "9309.3" not in blob or lock["not_table_5_4"] is True
    assert lock["forbidden_table_5_4_kN"] == [9309.3, 581.8]


def test_six_cases_include_construction_wind_and_gust():
    cases = json.loads((FORM / "six_cases.json").read_text())
    by_id = {c["id"]: c for c in cases["cases"]}
    assert set(by_id) == {1, 2, 3, 4, 5, 6}
    assert by_id[4]["has_wind"] is True
    assert by_id[4]["n_conload"] > 0
    assert by_id[5]["has_wind"] is True
    assert by_id[5]["n_conload"] > 0
    assert by_id[1]["has_wind"] is False
    assert by_id[2]["has_wind"] is False
    stld = cases["stld_sums"]
    assert "施工风荷载" in stld
    assert stld["施工风荷载"]["n_fy"] > 0
    assert abs(stld["施工风荷载"]["fz_kN"]) > 0
    assert "最大阵风" in stld


def test_p4_p5_daughters_carry_wind_cload():
    p4 = (FORM / "daughters" / "migrate_P4.inp").read_text(encoding="utf-8")
    p5 = (FORM / "daughters" / "migrate_P5.inp").read_text(encoding="utf-8")
    assert p4.count("*STEP, NLGEOM") == 2
    assert "*CLOAD" in p4
    assert "*CLOAD" in p5
    assert "表5-4" not in p4
    assert "0.0296" not in p4
    assert "TARGET-FREQ" not in p4
    p3 = (FORM / "daughters" / "migrate_P3.inp").read_text(encoding="utf-8")
    assert "*EXPANSION" in p3
    assert "*TEMPERATURE" in p3
    assert "N_MCT, -15" in p3


def test_dyn_is_perturbation_frequency_not_attachment_table():
    assert DYN_DAUGHTER.is_file()
    assert DYN.is_file()
    text = DYN.read_text(encoding="utf-8")
    assert "*STEP, PERTURBATION" in text
    assert "*FREQUENCY" in text
    assert "0.0296" not in text
    assert "TARGET-FREQ" not in text
    assert "9309.3" not in text
    isolated = ROOT / "isolated" / "TARGET-FREQ.json"
    tf = json.loads(isolated.read_text())
    for v in tf["values"]:
        assert str(v) not in text


def test_modeling_ledger_does_not_claim_attachment_fit():
    md = LEDGER.read_text(encoding="utf-8")
    ev = json.loads(EVIDENCE.read_text())
    assert "符合附件2-3" not in md
    assert ev.get("wrote_符合附件2-3") is False
    assert ev["main_sha256"] == MAIN_SHA
    assert ev["p1_sha256"] == P1_SHA
    assert ev["lock_force"]["n_iniforce"] == 1123
    assert ev.get("paper_written") is False
    assert ev.get("handoff") == "paper_post_formfind_layer_only"
    assert ev["gates"]["portal_mismatch_is_stop"] is False
    assert ev["gates"]["TARGET_FREQ_imported"] is False


def test_no_homemade_hash_is_current_main():
    data = json.loads(HASH_LEDGER.read_text())
    assert data["current_main_sha256"] == MAIN_SHA
    forbidden_prefixes = (
        "760c0ee4",
        "82548e6a",
        "41fb3222",
        "c635dad7",
        "6712e918",
        "be533c5f",
    )
    cur = data["current_main_sha256"]
    assert cur.startswith("974211b2")
    for h in forbidden_prefixes:
        assert not cur.startswith(h)
