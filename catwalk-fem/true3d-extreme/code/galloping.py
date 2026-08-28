#!/usr/bin/env python3
"""Steep-oscillation / galloping workshop (陡振).

Quasi-steady Den Hartog on the catwalk section using Attachment 2-3
table 3-1 coefficients copied in attach23_extract.json (comparison /
site-fill only; not imported by the solver).

H = dCl/dα + Cd   (α in rad).  H > 0 → no vertical galloping onset
from the linear criterion.  Across-wind wake galloping of a single
φ50 rope is a separate check using a literature Cd≈1.2 placeholder
and is flagged as 〔待填〕 (no section-model derivative for a lone rope).

Not a scientific claim. Does not announce 复现 against any event.
"""
from __future__ import annotations

import json
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
ART = BASE / "artifacts"
EXT = json.loads((ART / "attach23_extract.json").read_text())
CFG = json.loads((BASE / "config/site_wind.json").read_text())


def main() -> None:
    aero = EXT["static_coefficients_wind_axes_alpha0"]
    Cd = float(aero["CD"])
    dCl = float(EXT["dCL_dalpha_per_rad_approx"])
    H = dCl + Cd
    den_hartog = {
        "Cd_alpha0": Cd,
        "dCl_dalpha_per_rad": dCl,
        "H_den_hartog": H,
        "criterion": "H = dCl/dα + Cd; onset if H < 0",
        "verdict": "NO_ONSET_LINEAR" if H > 0 else "POSSIBLE_ONSET",
        "source": "artifacts/attach23_extract.json ← 附件2-3 表3-1, α=0; dCl from −3°…+3°",
        "note": "section model is the full catwalk (mesh+handrail), 1:10. Linear criterion only; no hysteresis / iced-cable case.",
    }
    # single-rope wake galloping: no Cl' in the extract → keep pending
    rope = {
        "spec": EXT["rope_break"]["spec"],
        "D_m": 0.050,
        "Cd_placeholder": 1.2,
        "dCl_dalpha": None,
        "verdict": "PENDING",
        "note": "〔待填:单索升力斜率；附件截面模型不是单索。不可用猫道整体 Cl' 代替。〕",
    }
    # critical wind sketch (Nauru / Parkinson form) left symbolic
    out = {
        "workshop": "steep_galloping_陡振",
        "catwalk_section": den_hartog,
        "single_bearing_rope": rope,
        "usage": "workshop diagnostic; does not drive the buffeting atlas",
        "claim": "not_a_scientific_conclusion",
    }
    dest = ART / "galloping_check.json"
    dest.write_text(json.dumps(out, indent=2, ensure_ascii=False))
    print(json.dumps(out, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
