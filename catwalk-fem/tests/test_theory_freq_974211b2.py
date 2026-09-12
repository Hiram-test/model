"""Theory-frequency layers on 974211b2.

Does not rewrite the main deck. Does not import isolated/TARGET-FREQ.json.
Does not treat 0.06438 as CCX. Does not write 符合附件2-3.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
THEORY = ROOT / "eval" / "theory_freq_974211b2"
MAIN = ROOT / "artifacts" / "zjg_catwalk_migrate_main.inp"
CLEARED = ROOT / "artifacts" / "zjg_catwalk_cleared.inp"
FREQ = ROOT / "eval" / "formfind_974211b2" / "FREQ.json"
ISOLATED = ROOT / "isolated" / "TARGET-FREQ.json"

MAIN_SHA = "974211b2ddfe2950548ee2455bc22e1e2e68d3e1f53df4c4e1eb71ece0267fd1"
CLEARED_SHA = "760c0ee44d7077ddfb84273cba916abb1fea1eb2a0ff6cfe57abaec9b0585de9"
CCX_F1 = 0.1335403

sys.path.insert(0, str(THEORY))
from common import (  # noqa: E402
    ATT_F1,
    FORBIDDEN_HALF,
    G_MCT,
    irvine_inplane_freqs,
    irvine_lambda2,
    sag_freq,
    sha256_file,
    taut_freq,
)


def test_main_and_cleared_untouched():
    assert MAIN.is_file()
    assert sha256_file(MAIN) == MAIN_SHA
    assert MAIN.stat().st_size == 930300
    assert sha256_file(CLEARED) == CLEARED_SHA


def test_ccx_f1_is_the_locked_root_not_the_discarded_half():
    freq = json.loads(FREQ.read_text())
    assert freq["freq_cycles"][0] == pytest.approx(CCX_F1, abs=1e-7)
    assert freq["compared_to_attachment_2_3"] is False
    assert freq["imported_TARGET_FREQ"] is False
    assert abs(freq["freq_cycles"][0] - FORBIDDEN_HALF) > 1e-4


def test_sag_and_taut_closed_form():
    assert sag_freq(1, 227.3, G_MCT) == pytest.approx(math.sqrt(G_MCT / (32.0 * 227.3)))
    f = taut_freq(1, 2302.0, 10431682.050847458, 282.044570937506)
    assert f == pytest.approx(0.04177178015572532, rel=1e-12)


def test_irvine_drops_trivial_root_and_sits_above_antisym_for_large_lambda2():
    L, d = 2302.0, 227.3
    H, mu, EA = 10431682.050847458, 282.044570937506, 2675843040.0
    lam2 = irvine_lambda2(d, L, H, EA)
    assert lam2 > 4.0 * math.pi**2
    irv = irvine_inplane_freqs(L, d, H, mu, EA, n_sym=2, n_antisym=1)
    assert irv["symmetric"][0]["Omega"] > 6.0
    assert irv["first_inplane_Hz"] == pytest.approx(irv["antisymmetric"][0]["f_Hz"])
    assert 2.5 < irv["symmetric"][0]["f_over_ftaut"] < 2.9


def test_layers_exist_and_do_not_claim_fit():
    for name in (
        "MODELING.md",
        "params.json",
        "layer1.json",
        "layer2.json",
        "layer3.json",
        "layer4.json",
        "COMPARE.json",
        "spectrum.svg",
        "run.py",
        "layer1_two_cable.py",
        "layer2_dual_mct.py",
        "layer3_passages.py",
        "layer4_four_span.py",
    ):
        assert (THEORY / name).is_file()
    md = (THEORY / "MODELING.md").read_text(encoding="utf-8")
    assert "符合附件2-3" not in md
    assert "0.06438" in md
    assert "不成稿" in md
    compare = json.loads((THEORY / "COMPARE.json").read_text())
    assert compare["wrote_符合"] is False
    assert compare["scientific_success"] is False
    assert compare["imported_TARGET_FREQ"] is False
    assert compare["used_0.06438"] is False
    assert compare["main_sha256"] == MAIN_SHA
    params = json.loads((THEORY / "params.json").read_text())
    assert params["imported_TARGET_FREQ"] is False
    assert params["used_0.06438_as_ccx"] is False
    isolated = json.loads(ISOLATED.read_text())
    assert isolated["values"][0] == ATT_F1
    assert "TARGET-FREQ" not in json.dumps(params.get("main"))


def test_self_judge_points_south_span_at_ccx_and_sag_band_at_attachment():
    compare = json.loads((THEORY / "COMPARE.json").read_text())
    assert compare["nearest_to_ccx_f1"]["name"] == "south_span_floor_n1"
    assert abs(compare["nearest_to_ccx_f1"]["vs_0.1335403_rel"]) < 0.01
    assert compare["nearest_to_0.0296"]["name"] == "torsion_sagH_n1"
    l2 = json.loads((THEORY / "layer2.json").read_text())
    assert l2["self_judge"]["nearest_ccx_0.1335403"] == "south_span_floor_n1"
    assert l2["self_judge"]["optical_is_out_of_band"] is True
    l3 = json.loads((THEORY / "layer3.json").read_text())
    assert l3["ccx_can_realise"] is False
    assert l3["inputs"]["k_for_att_split_physical"] is False
    l4 = json.loads((THEORY / "layer4.json").read_text())
    assert l4["ccx_matches"][0]["nearest"].startswith("南边跨")
    assert l4["highlights"]["main_taut_n1_in_ccx_first20"] is False


def test_run_is_deterministic_enough_to_rebuild_compare():
    import run as theory_run

    out = theory_run.main()
    assert out["ccx_f1_Hz"] == CCX_F1
    assert sha256_file(MAIN) == MAIN_SHA
