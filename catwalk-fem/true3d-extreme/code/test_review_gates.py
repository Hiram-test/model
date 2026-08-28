#!/usr/bin/env python3
"""Lightweight review gates that do not need ccx or S10 sources."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import numpy as np

import build_true3d_ccx as builder
import pair_table41 as pairing
import postprocess_modes as pp
import write_gate_status as gates

BASE = Path(__file__).resolve().parent.parent
CODE = BASE / "code"
ART = BASE / "artifacts"
REPO = BASE.parent.parent


def test_weather_library_conversion_lock():
    lib = json.loads((ART / "extreme_weather_library.json").read_text())
    sc = {s["id"]: s for s in lib["scenarios"]}
    assert len(sc) == 43
    assert abs(sc["ss_cat1"]["U10_sustained_ms"] - 33.0 / 1.14) < 0.05
    assert abs(sc["infa_2021_zhoushan"]["U10_sustained_ms"] - 38.0 / 1.06) < 0.05
    assert abs(sc["doksuri_2023_jinjiang"]["U10_sustained_ms"] - 50.0 / 1.06) < 0.05
    assert abs(sc["amphan_2020_peak"]["U10_sustained_ms"] - 66.7 / 1.05) < 0.05
    assert abs(sc["ef3_anchor"]["U10_sustained_ms"] - 67.0 / 1.42) < 0.05
    schema = lib["schema"]["U10_sustained_ms"]
    for token in ("/1.14", "/1.06", "/1.05", "/1.42"):
        assert token in schema
    c_rows = [s for s in lib["scenarios"] if s["confidence"] == "C"]
    assert len(c_rows) == 15
    assert all(s.get("source") for s in lib["scenarios"])
    blob = json.dumps(lib, ensure_ascii=False)
    assert "颱" not in blob, "library is simplified Chinese; do not write 颱"
    for s in lib["scenarios"]:
        if s["category"] == "hurricane":
            assert "台风" not in s["name_cn"] and "颱风" not in s["name_cn"], s["id"]
    ledger = json.loads((ART / "c_level_review.json").read_text())
    assert "15" in ledger["rule"]
    assert {s["id"] for s in c_rows} == {x["id"] for x in ledger["items"]}


def test_isolation_no_attach23_in_solver_scripts():
    banned = ("attach23_extract.json", "0.0996", "lat_rms_m", "table_5_1")
    for name in ("build_true3d_ccx.py", "parse_s10.py", "run_solver.sh", "buffeting.py"):
        text = (CODE / name).read_text()
        for token in banned:
            assert token not in text, f"{name} must not carry attachment 2-3 comparison numbers"


def test_no_nall_totals():
    text = (CODE / "build_true3d_ccx.py").read_text()
    assert text.count("\n") > 400, "builder was emptied; restore from last good commit"
    assert "def main" in text and "def nid" in text
    assert "*NODE PRINT, NSET=NALL" not in text
    assert "*NODE PRINT, NSET=NSUPP, TOTALS" not in text
    assert "*NODE PRINT, NSET=NSUPP" in text
    assert "TYPE=MASS" not in text
    assert "T3D2" not in text or "禁 T3D2" in text or "not T3D2" in text.lower()
    assert "SECTION=RECT" in text


def test_s10_ids_do_not_clobber_builder_scheme():
    assert builder.deck_id_from_s10(8) == 8
    assert builder.deck_id_from_s10(99999) == 99999
    assert builder.deck_id_from_s10(100000) == 2_000_000 + 100000
    assert builder.deck_id_from_s10(2029623) == 2_000_000 + 2029623
    rope = 100000 * 1 + 12
    assert builder.deck_id_from_s10(rope) != rope
    mass_csv = REPO / (
        "catwalk-fem/double-mct-buffeting/inputs/roll_upgrade_sources/"
        "mass21_spatialized_v2_nodes.csv"
    )
    ids = []
    with open(mass_csv) as f:
        f.readline()
        for line in f:
            ids.append(int(line.split(",")[0]))
    assert max(ids) > 100000
    remapped = {builder.deck_id_from_s10(n) for n in ids}
    scheme = {100000 * (g + 1) + k for g in range(8) for k in range(5000)}
    assert remapped.isdisjoint(scheme)


def test_r5_passage_cluster_is_21():
    raw = []
    for i in range(21):
        x0 = 100000.0 + i * 150000.0
        raw.extend([x0, x0 + 700.0, x0 + 1400.0])
    clustered = builder.cluster_x_stations(raw, gap=5000.0)
    assert len(raw) == 63
    assert len(clustered) == 21


def test_station_k_torsion_alignment():
    a = {"x": np.array([0.0, 10.0, 20.0]), "uz": np.array([0.0, 1.0, 2.0]),
         "k": np.array([2, 0, 1])}
    b = {"x": np.array([20.0, 0.0, 10.0]), "uz": np.array([5.0, 3.0, 4.0]),
         "k": np.array([1, 2, 0])}
    xs, duz = pp._align_by_station_k(a, b, "uz")
    assert list(xs) == [0.0, 10.0, 20.0]
    assert list(duz) == [3.0, 3.0, 3.0]


def test_pairing_locked_keys_no_ts3():
    assert "TS3" not in pairing.MAIN_ROWS
    assert pairing.MAIN_ROWS["TS2"] == ("T", "S", 2)
    assert pairing.MAIN_ROWS["LS2"] == ("L", "S", 2)
    ref = REPO / (
        "catwalk-fem/double-mct-buffeting/inputs/roll_upgrade_sources/"
        "reference_attachment_2_3_table4_1.csv"
    )
    header = ref.read_text().splitlines()[0]
    assert "internal_id" in header and "frequency_hz" in header


def test_site_wind_v1_from_extract_not_placeholder():
    cfg = json.loads((BASE / "config/site_wind.json").read_text())
    assert cfg["aero"]["placeholder_values_used_if_missing"] is False
    assert abs(cfg["aero"]["catwalk_per_band"]["Cd_D_m"] - 0.39453675) < 1e-9
    assert cfg["structure"]["rope_break_force_kN_per_bearing_rope"] == 2380.0
    extract = json.loads((ART / "attach23_extract.json").read_text())
    assert "table_5_1_V10_30p1_ms" in extract
    assert "lat_rms_m" not in (CODE / "build_true3d_ccx.py").read_text()


def test_buffeting_four_channels_and_air_density():
    text = (CODE / "buffeting.py").read_text()
    assert "RHO = 1.225e-12" in text
    assert "Tcw" in text and "0.5772" in text
    sweep = (CODE / "sweep_extreme.py").read_text()
    assert "tornado" in sweep and "downburst" in sweep and "derecho" in sweep


def test_gp4_does_not_relax_1e6():
    assert gates.FORCE_OVER_W_MAX == 1e-6
    ok = gates.gp4_verdict(0, 1e-6)
    assert ok["pass"] and ok["verdict"] == "PASS"
    force_fail = gates.gp4_verdict(0, 1.42e-6)
    assert not force_fail["pass"]
    assert not force_fail["pass_force_1e-6"]
    assert "FAIL" in force_fail["verdict"]
    zeros = gates.gp4_verdict(4, 1e-7)
    assert not zeros["pass"]
    src = (CODE / "write_gate_status.py").read_text()
    assert "1e-5" not in src
    assert "STRUCTURAL_OK" not in src


def test_wave4_required_ancestor():
    """Later work must stay on top of the completed wave-4 SHA."""
    pin = (BASE / "WAVE4_REQUIRED_ANCESTOR").read_text()
    sha = None
    for line in pin.splitlines():
        if line.startswith("REQUIRED_ANCESTOR="):
            sha = line.split("=", 1)[1].strip()
    assert sha == "3a4250e9f01f41c198967eaa685e497134573049"
    assert hasattr(builder, "deck_id_from_s10")
    assert hasattr(builder, "cluster_x_stations")
    assert hasattr(pp, "_align_by_station_k")
    assert hasattr(gates, "FORCE_OVER_W_MAX")
    r = subprocess.run(
        ["git", "merge-base", "--is-ancestor", sha, "HEAD"],
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    if r.returncode == 128:
        return
    assert r.returncode == 0, (
        f"HEAD is not a descendant of wave-4 {sha}; "
        "rebase onto that SHA before any new work"
    )


def test_run_status_and_baseline_lock():
    run = (ART / "RUN_STATUS.md").read_text()
    assert "STRUCTURAL_OK" not in run
    assert "FAIL" in run
    assert (BASE / "REVIEW_BASELINE.md").is_file()
    assert "3a4250e9" in (BASE / "REVIEW_BASELINE.md").read_text()
    plan = (BASE / "FOLLOW_FABLE_PLAN.txt").read_text()
    assert "WAVE4_REQUIRED_ANCESTOR" in plan
    assert "test_review_gates.py" in plan
    assert "3a4250e9" in plan


def test_coarsen2_ledger_cited_and_portal_glyph():
    """COARSEN=2 already ran; W1 must cite the ledger. Portal unit is 榀."""
    shift = json.loads((ART / "coarsen2_shift.json").read_text())
    assert "TA1" in shift["T_shift"]
    w1 = (BASE / "workshops/W1_structure.md").read_text()
    assert "coarsen2_shift.json" in w1
    assert "未跑" not in w1
    assert "榀" in w1
    assert "棱" not in w1
    assert "椄" not in w1
    assert "榌" not in w1


def test_master_cv_gate_not_relaxed():
    cv = json.loads((ART / "atlas/master_surface_cv.json").read_text())
    assert cv["threshold"] == 0.05
    assert cv["n_stationary"] + cv["n_reference_only"] == 43
    assert cv["max_rel"] < 0.05
    warn = json.loads((ART / "warning_demo_sutong.json").read_text())
    assert warn["LEVEL"] == "NOT_ARMED"
    assert "待填" in warn["reason"]


def main() -> None:
    test_weather_library_conversion_lock()
    test_isolation_no_attach23_in_solver_scripts()
    test_no_nall_totals()
    test_s10_ids_do_not_clobber_builder_scheme()
    test_r5_passage_cluster_is_21()
    test_station_k_torsion_alignment()
    test_pairing_locked_keys_no_ts3()
    test_site_wind_v1_from_extract_not_placeholder()
    test_buffeting_four_channels_and_air_density()
    test_gp4_does_not_relax_1e6()
    test_wave4_required_ancestor()
    test_run_status_and_baseline_lock()
    test_coarsen2_ledger_cited_and_portal_glyph()
    test_master_cv_gate_not_relaxed()
    print("review gates PASS")


if __name__ == "__main__":
    main()
