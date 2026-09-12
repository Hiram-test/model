"""Clear-four B31: freeze 82548e6a / 41fb3222 / c635dad7; new hash 760c0ee4; unc==0."""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / "pipeline"))

from clear_four_b31 import (  # noqa: E402
    CLEARED_BYTES,
    CLEARED_NAME,
    CLEARED_SHA256,
    CLEAR_NSET,
    GIVEN_FOUR,
    SITE_41FB_SHA256,
    SITE_C635_NAME,
    SITE_C635_SHA256,
    emit_cleared,
    parse_mesh,
    unconstrained_components,
)
from reread_cleared import (  # noqa: E402
    EXPECTED_CROSS_PASSAGE,
    EXPECTED_DRAWING_STUBS,
    EXPECTED_IC_ROWS,
    parse_elset,
    reread_pair,
    stream_ic,
)
from reread_deck import FROZEN_SHA256, sha256_file  # noqa: E402


ART = HERE / "artifacts"
FROZEN = ART / "zjg_catwalk_coarsened.inp"
SITE41 = ART / "zjg_catwalk_ccx221.inp"
SITE_C635 = ART / SITE_C635_NAME
CLEARED = ART / CLEARED_NAME


def test_three_frozen_hashes_untouched():
    assert sha256_file(FROZEN) == FROZEN_SHA256
    assert sha256_file(SITE41) == SITE_41FB_SHA256
    assert sha256_file(SITE_C635) == SITE_C635_SHA256
    assert FROZEN.stat().st_size == 7_702_117
    assert SITE41.stat().st_size == 26_839_981
    assert SITE_C635.stat().st_size == 47_948_333
    text = SITE_C635.read_text(encoding="utf-8")
    assert CLEAR_NSET not in text


def test_refuse_overwrite_frozen_paths(tmp_path: Path | None = None):
    for dest in (FROZEN, SITE41, SITE_C635):
        try:
            emit_cleared(SITE_C635, dest)
        except SystemExit as exc:
            assert "REFUSING" in str(exc)
        else:
            raise AssertionError(f"emit_cleared must refuse dest {dest}")
        assert sha256_file(FROZEN) == FROZEN_SHA256
        assert sha256_file(SITE41) == SITE_41FB_SHA256
        assert sha256_file(SITE_C635) == SITE_C635_SHA256


def test_refuse_wrong_source(tmp_path: Path):
    dest = Path(tmp_path) / "should_not_exist.inp"
    try:
        emit_cleared(SITE41, dest)
    except SystemExit as exc:
        assert "source is not c635dad7" in str(exc)
    else:
        raise AssertionError("emit_cleared must refuse a non-c635 source")
    assert not dest.exists()
    assert sha256_file(SITE41) == SITE_41FB_SHA256


def test_c635_still_has_given_four_b31():
    mesh = parse_mesh(SITE_C635)
    unc = unconstrained_components(mesh)
    nodes = sorted({n for c in unc for n in c})
    assert len(unc) == 4
    assert len(nodes) == 12
    assert nodes == GIVEN_FOUR["nodes"]


def test_cleared_hash_and_zero_unconstrained():
    assert CLEARED.is_file()
    assert sha256_file(CLEARED) == CLEARED_SHA256
    assert CLEARED.stat().st_size == CLEARED_BYTES
    sidecar = CLEARED.with_suffix(CLEARED.suffix + ".sha256")
    assert sidecar.read_text(encoding="utf-8").split()[0] == CLEARED_SHA256
    mesh = parse_mesh(CLEARED)
    unc = unconstrained_components(mesh)
    assert unc == []
    assert mesh["nsets"].get(CLEAR_NSET, []) == GIVEN_FOUR["nodes"]
    assert CLEAR_NSET in mesh["bc_sets"]
    floor = set(mesh["nsets"]["N_FLOOR_ANCHOR"])
    portal = set(mesh["nsets"]["N_PORTAL_ANCHOR"])
    assert len(floor) == 312
    assert len(portal) == 16
    assert not (floor & portal)
    assert len(parse_elset(CLEARED, "E_CROSS_PASSAGE")) == EXPECTED_CROSS_PASSAGE


def test_ic_still_421432_eight_field():
    ic = stream_ic(CLEARED)
    assert ic["n_rows"] == EXPECTED_IC_ROWS
    assert ic["n_ccx221_legal"] == EXPECTED_IC_ROWS
    assert ic["n_elset_uniaxial"] == 0
    assert ic["all_ccx221_legal"]
    assert not ic["any_elset_uniaxial"]
    assert ic["all_ic_elements_have_8_ips"]
    assert ic["first_row"].startswith("1, 1, 1.439957e+08")
    ic_fail = stream_ic(SITE_C635)
    assert ic_fail["n_rows"] == EXPECTED_IC_ROWS
    assert ic_fail["first_row"] == ic["first_row"]


def test_independent_reread_pass():
    rec = reread_pair()
    assert rec["pass"], rec
    assert rec["cleared"]["drawing_stubs"]["n"] == EXPECTED_DRAWING_STUBS
    assert rec["cleared"]["heading"]["portals_142_correct_glyph"]
    assert rec["ccx_ran"] is False
    assert rec["pushed"] is False
    assert rec["merged"] is False
    assert rec["frozen_untouched"]["41fb3222"]
    assert rec["frozen_untouched"]["c635dad7"]


if __name__ == "__main__":
    from pathlib import Path as _P

    test_three_frozen_hashes_untouched()
    test_refuse_overwrite_frozen_paths()
    test_refuse_wrong_source(_P("/tmp"))
    test_c635_still_has_given_four_b31()
    test_cleared_hash_and_zero_unconstrained()
    test_ic_still_421432_eight_field()
    test_independent_reread_pass()
    print("test_clear_four_b31 ok")
