"""Plan + MCT alignment overlay for 974211b2. Does not rewrite the main."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "eval" / "plan_974211b2"
MAIN = ROOT / "artifacts" / "zjg_catwalk_migrate_main.inp"
CLEARED = ROOT / "artifacts" / "zjg_catwalk_cleared.inp"
MAIN_SHA = "974211b2ddfe2950548ee2455bc22e1e2e68d3e1f53df4c4e1eb71ece0267fd1"
CLEARED_SHA = "760c0ee44d7077ddfb84273cba916abb1fea1eb2a0ff6cfe57abaec9b0585de9"

sys.path.insert(0, str(PLAN))
from overlay import run  # noqa: E402


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_plan_exists_on_pr19_path():
    text = (PLAN / "PLAN.md").read_text(encoding="utf-8")
    assert "974211b2" in text
    assert "机构型" in text
    assert "不锁稿" in text
    assert "703.46" in text
    assert "demo-rl-calculix" in text


def test_overlay_closes_on_main_without_rewrite():
    ev = run()
    assert ev["overlay"]["main"]["sha256"] == MAIN_SHA
    assert ev["overlay"]["main"]["rewritten"] is False
    assert ev["frozen"]["untouched"] is True
    assert ev["alignment"]["drawing_absent"] is True
    pk = ev["overlay"]["pk2_vs_main_ip1_abs_rel"]
    assert pk["n"] == 1123
    assert pk["max"] < 1e-6
    sig = ev["overlay"]["source_sigma_eid1_not_locked"]
    assert sig["lock_manuscript"] is False
    assert abs(sig["sigma_from_INI_EFORCE_N_mm2"] - 703.4605548416231) < 1e-9
    spans = {s["group"]: s for s in ev["alignment"]["floor_spans"]}
    assert abs(spans["主跨"]["L_m"] - 2302.0) < 1e-9
    assert abs(spans["主跨"]["sag_end_minus_zmin_m"] - 227.297397) < 1e-5
    assert ev["acknowledged_linear_static"]["lock_703_46"] is False
    assert ev["acknowledged_linear_static"]["S_approx_IC_is_not_equilibrium"] is True
    assert ev["twisted_to_demo_rl_calculix"] is False


def test_bytes_untouched():
    assert _sha(MAIN) == MAIN_SHA
    assert _sha(CLEARED) == CLEARED_SHA


def test_written_json_if_present():
    p = PLAN / "overlay.json"
    if not p.is_file():
        return
    data = json.loads(p.read_text(encoding="utf-8"))
    assert data["main"]["sha256"] == MAIN_SHA
    assert data["source_sigma_eid1_not_locked"]["lock_manuscript"] is False


if __name__ == "__main__":
    test_plan_exists_on_pr19_path()
    test_overlay_closes_on_main_without_rewrite()
    test_bytes_untouched()
    test_written_json_if_present()
    print("ok")
