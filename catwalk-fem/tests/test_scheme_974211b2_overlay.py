"""Reread the 974211b2 overlay scheme. Does not rewrite any .inp."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOST = ROOT / "artifacts" / "zjg_catwalk_migrate_main.inp"
CLEARED = ROOT / "artifacts" / "zjg_catwalk_cleared.inp"
MCT = ROOT / "mct-from-zero" / "source" / "01_设计资料与规范" / "猫道 - 门架索合建模型2.mct"
SCHEME_JSON = ROOT / "eval" / "SCHEME_974211b2_LINE_OVERLAY.json"
SCHEME_MD = ROOT / "eval" / "SCHEME_974211b2_LINE_OVERLAY.md"
ISOLATED = ROOT / "isolated" / "TARGET-FREQ.json"
SKILLS = ROOT.parents[0] / "bridge-fem-skill-suite" / "skills"

HOST_SHA = "974211b2ddfe2950548ee2455bc22e1e2e68d3e1f53df4c4e1eb71ece0267fd1"
CLEARED_SHA = "760c0ee44d7077ddfb84273cba916abb1fea1eb2a0ff6cfe57abaec9b0585de9"
MCT_SHA = "0d18e3f7b009e0306fb4b9f3051b4a16d05fa24d9e966774e809b8942a4f22e1"

PINS = {
    1001: (831091.0, 44310.0),
    1: (852105.0, 28152.0),
    157: (1542679.0, 340600.0),
    160: (1553300.0, 334645.0),
    302: (2686000.0, 113300.0),
    444: (3818700.0, 334537.0),
    447: (3829321.0, 340600.0),
    1395: (5101700.0, 41317.0),
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_nodes(text: str) -> dict[int, tuple[float, float, float]]:
    nodes: dict[int, tuple[float, float, float]] = {}
    in_node = False
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("*"):
            in_node = line.upper().startswith("*NODE") and "TRANSFORM" not in line.upper()
            continue
        if not in_node or not line or line.startswith("**"):
            continue
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 4:
            continue
        nodes[int(parts[0])] = (float(parts[1]), float(parts[2]), float(parts[3]))
    return nodes


def test_hashes_and_frozen():
    assert sha256(HOST) == HOST_SHA
    assert HOST.stat().st_size == 930300
    assert sha256(CLEARED) == CLEARED_SHA
    assert sha256(MCT) == MCT_SHA
    assert MCT.name == "猫道 - 门架索合建模型2.mct"
    book = (ROOT / "artifacts" / "checksums.sha256").read_text(encoding="utf-8")
    assert f"{HOST_SHA}  zjg_catwalk_migrate_main.inp" in book
    assert f"{CLEARED_SHA}  zjg_catwalk_cleared.inp" in book
    ledger = json.loads((ROOT / "artifacts" / "HASH_LEDGER.json").read_text(encoding="utf-8"))
    roles = {e["role"]: e["sha256"] for e in ledger["entries"]}
    assert roles["current_main"] == HOST_SHA
    assert roles["frozen_cleared_site"] == CLEARED_SHA
    assert ledger["current_main_sha256"] == HOST_SHA
    assert "SCHEME_974211b2_LINE_OVERLAY.md" in ledger.get("scheme", "")


def test_scheme_json_covers_backbone():
    doc = json.loads(SCHEME_JSON.read_text(encoding="utf-8"))
    assert doc["kind"] == "scheme_974211b2_line_overlay"
    assert doc["rewrote_974211b2"] is False
    assert doc["rewrote_760c0ee4"] is False
    assert doc["imported_target_freq_into_objective"] is False
    assert doc["invented_s10_cable_force"] is False
    assert doc["twisted_to_demo_rl_calculix"] is False
    assert doc["given_paths"]["host_main"]["sha256"] == HOST_SHA
    assert doc["visual_lock"]["N_primary"] == 8
    assert doc["visual_lock"]["forbidden_N"] == 1123
    assert doc["visual_lock"]["pin_table_1_9_already_on_host"] is True
    ids = [s["id"] for s in doc["steps"]]
    assert ids == [f"N{i:02d}" for i in range(19)]
    assert len(list(SKILLS.glob("*/SKILL.md"))) == 19
    assert doc["calibration"]["pso"]["otherwise"] == "NOT_APPLICABLE"
    assert doc["swap_once"]["host_readonly"] is True


def test_scheme_does_not_feed_isolated_freq():
    isolated = json.loads(ISOLATED.read_text(encoding="utf-8"))
    md = SCHEME_MD.read_text(encoding="utf-8")
    js = SCHEME_JSON.read_text(encoding="utf-8")
    for value in isolated["values"]:
        token = f"{value:.4f}".rstrip("0").rstrip(".")
        if token == "0":
            continue
        assert f"{value:.4f}" not in md
        assert f"{value:.4f}" not in js
    assert "demo-rl-calculix" in md
    assert "不扭" in md or "twisted_to_demo_rl_calculix" in js


def test_host_pins_match_table_1_9():
    nodes = parse_nodes(HOST.read_text(encoding="latin-1"))
    for nid, (x, z) in PINS.items():
        assert nid in nodes, nid
        xn, yn, zn = nodes[nid]
        assert abs(xn - x) < 1e-6, (nid, xn, x)
        assert abs(zn - z) < 1e-3, (nid, zn, z)
        assert abs(yn) < 1e-6
    mid_x_homemade = nodes[302][0] / 1000.0 - 876.0
    assert abs(mid_x_homemade - 1810.0) < 1e-9


def test_markdown_present():
    text = SCHEME_MD.read_text(encoding="utf-8")
    assert "974211b2" in text
    assert "逻辑主干" in text
    assert "一次交换" in text
    assert "N10" in text
    assert "760c0ee4" in text


if __name__ == "__main__":
    test_hashes_and_frozen()
    test_scheme_json_covers_backbone()
    test_scheme_does_not_feed_isolated_freq()
    test_host_pins_match_table_1_9()
    test_markdown_present()
    print("test_scheme_974211b2_overlay ok")
    sys.exit(0)
