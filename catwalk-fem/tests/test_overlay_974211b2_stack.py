"""MCT alignment stacked on 974211b2. Does not rewrite the main."""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / "eval" / "overlay_974211b2"
MAIN = ROOT / "artifacts" / "zjg_catwalk_migrate_main.inp"
CLEARED = ROOT / "artifacts" / "zjg_catwalk_cleared.inp"
MAIN_SHA = "974211b2ddfe2950548ee2455bc22e1e2e68d3e1f53df4c4e1eb71ece0267fd1"
CLEARED_SHA = "760c0ee44d7077ddfb84273cba916abb1fea1eb2a0ff6cfe57abaec9b0585de9"

sys.path.insert(0, str(HERE))
from stack import run  # noqa: E402


def test_stack_closes_without_rewrite():
    out = run()
    s = out["stack"]
    assert s["main_sha256"] == MAIN_SHA
    assert s["main_rewritten"] is False
    assert s["cleared_untouched"] is True
    assert s["nodes"]["missing"] == 0
    assert s["nodes"]["reprint_miss"] == 0
    assert s["elems"]["connectivity_miss"] == 0
    assert s["elems"]["type_miss"] == 0
    assert s["prestress_ic"]["n"] == 1123
    assert s["prestress_ic"]["missing"] == 0
    assert s["prestress_ic"]["max_abs_rel"] < 1e-6
    assert s["boundary"]["missing"] == 0
    assert s["boundary"]["extra"] == 0
    assert s["cload_erqi"]["missing"] == 0
    assert s["cload_erqi"]["extra"] == 0
    assert s["cload_erqi"]["max_abs_rel"] < 1e-8
    spans = {p["group"]: p for p in out["floor"]}
    assert spans["主跨"]["n_pts"] == 296
    assert abs(spans["主跨"]["x1"] if False else spans["主跨"]["x1_m"] - spans["主跨"]["x0_m"] - 2302.0) < 1e-9
    assert hashlib.sha256(MAIN.read_bytes()).hexdigest() == MAIN_SHA
    assert hashlib.sha256(CLEARED.read_bytes()).hexdigest() == CLEARED_SHA


if __name__ == "__main__":
    test_stack_closes_without_rewrite()
    print("ok")
