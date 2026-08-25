"""Frozen deck 82548e6a must stay unread-write; IC is ELSET+uniaxial; 142 榀 close."""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / "pipeline"))

from audit_frozen_deck import (  # noqa: E402
    FROZEN_SHA256,
    audit_frozen_inp,
    classify_ic_line,
    portal_ledger_summary,
)
from reconcile import sha256_file  # noqa: E402
import json  # noqa: E402


def test_classify_elset_uniaxial():
    row = classify_ic_line("E_FLOOR_ROPE, 3.549611e+08")
    assert row["elset_plus_uniaxial"] is True
    assert row["ccx_2_21_legal"] is False
    legal = classify_ic_line("12, 1, 3.55e8, 0, 0, 0, 0, 0")
    assert legal["ccx_2_21_legal"] is True


def test_frozen_inp_not_rewritten():
    inp = HERE / "artifacts" / "zjg_catwalk_coarsened.inp"
    before = sha256_file(inp)
    assert before == FROZEN_SHA256
    deck = audit_frozen_inp(inp)
    after = sha256_file(inp)
    assert after == before == FROZEN_SHA256
    assert deck["hash_unchanged"]
    assert deck["deck_ic_is_elset_uniaxial"]
    assert deck["anchors_disjoint"]
    assert deck["n_floor_anchor"] == 312
    assert deck["n_portal_anchor"] == 16
    floor = deck["initial_conditions"]["rows"][0]
    assert floor["first_token"] == "E_FLOOR_ROPE"
    assert abs(float(floor["fields"][1]) - 3.549611e8) < 1.0
    assert deck["has_25556"] is False
    assert deck["has_00296"] is False


def test_142_portals_are_frames_not_wrong_glyph():
    ledger = json.loads((HERE / "artifacts" / "portal_142_ledger.json").read_text())
    summary = portal_ledger_summary(ledger)
    assert summary["unit"] == "榀"
    assert summary["not_unit"] == "槇"
    assert summary["pass_142"]
    assert summary["drawing_stations"] == 71
    assert summary["both_decks_hit"] == 142
    assert summary["n_missing"] == 0
    assert summary["inserted_portals"] == 0
    assert summary["by_span_stations"] == {
        "north_660": 11,
        "main_2300": 41,
        "south_717": 11,
        "south_503": 8,
    }


if __name__ == "__main__":
    test_classify_elset_uniaxial()
    test_frozen_inp_not_rewritten()
    test_142_portals_are_frames_not_wrong_glyph()
    print("test_audit_frozen_deck ok")
