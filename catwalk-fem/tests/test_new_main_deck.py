"""New main deck must be §7.76 PK2; frozen 82548e6a stays untouched."""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / "pipeline"))

from reread_deck import FROZEN_SHA256, compare_frozen_untouched, reread_inp  # noqa: E402
from write_inp import write_calculix_inp  # noqa: E402
from test_write_inp import _toy_mesh  # noqa: E402


def test_frozen_bytes_still_82548e6a():
    frozen = HERE / "artifacts" / "zjg_catwalk_coarsened.inp"
    rec = compare_frozen_untouched(frozen)
    assert rec["untouched"], rec
    rr = reread_inp(frozen)
    assert rr["is_frozen_82548e6a"]
    assert rr["initial_conditions"]["any_elset_uniaxial"]
    assert not rr["initial_conditions"]["all_ccx221_legal"]
    assert rr["initial_conditions"]["first_row"]["first_token"] == "E_FLOOR_ROPE"


def test_writer_toy_is_ccx221_pk2(tmp_path: Path | None = None):
    out = (tmp_path or Path("/tmp")) / "toy_ccx221.inp"
    meta = write_calculix_inp(_toy_mesh(), out, include_frequency=False)
    rr = reread_inp(out)
    assert rr["initial_conditions"]["all_ccx221_legal"]
    assert not rr["initial_conditions"]["any_elset_uniaxial"]
    assert rr["initial_conditions"]["first_tokens_are_element_numbers"]
    assert rr["sha256"] != FROZEN_SHA256
    assert meta["ic_ccx_2_21_legal"]
    assert rr["anchors_disjoint"]


def test_new_main_deck_if_present():
    new = HERE / "artifacts" / "zjg_catwalk_ccx221.inp"
    frozen = HERE / "artifacts" / "zjg_catwalk_coarsened.inp"
    assert compare_frozen_untouched(frozen)["untouched"]
    if not new.is_file():
        return
    rr = reread_inp(new)
    assert not rr["is_frozen_82548e6a"]
    assert rr["initial_conditions"]["all_ccx221_legal"]
    assert not rr["initial_conditions"]["any_elset_uniaxial"]
    assert rr["heading_has_k16876"]
    assert rr["anchors_disjoint"]
    assert rr["has_25556"] is False
    assert rr["has_target_freq_values"] is False
    assert compare_frozen_untouched(frozen)["untouched"]


if __name__ == "__main__":
    test_frozen_bytes_still_82548e6a()
    test_writer_toy_is_ccx221_pk2()
    test_new_main_deck_if_present()
    print("test_new_main_deck ok")
