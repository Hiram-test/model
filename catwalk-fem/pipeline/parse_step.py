"""Stream-parse a FreeCAD/OCC centerline STEP into metre segments."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

import numpy as np

try:
    from .constants import STEP_SHA256
except ImportError:
    from constants import STEP_SHA256

POINT_RE = re.compile(
    r"#(\d+)\s*=\s*CARTESIAN_POINT\s*\(\s*'[^']*'\s*,\s*\(\s*([^)]+?)\s*\)",
    re.S,
)
CURVE_RE = re.compile(
    r"#\d+\s*=\s*TRIMMED_CURVE\s*\(\s*'[^']*'\s*,\s*#\d+\s*,\s*"
    r"\(\s*#(\d+)\s*,\s*PARAMETER_VALUE\s*\([^)]*\)\s*\)\s*,\s*"
    r"\(\s*#(\d+)\s*,\s*PARAMETER_VALUE\s*\([^)]*\)\s*\)",
    re.S,
)
UNIT_RE = re.compile(r"SI_UNIT\s*\(\s*\.([A-Z]+)\.\s*,\s*\.METRE\.")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _scale_from_unit(prefix: str | None) -> float:
    if prefix is None or prefix == "ONE":
        return 1.0
    if prefix == "MILLI":
        return 1.0e-3
    if prefix == "CENTI":
        return 1.0e-2
    if prefix == "KILO":
        return 1.0e3
    raise ValueError(f"unsupported SI_UNIT prefix {prefix!r}")


def parse_step(path: Path, expected_sha256: str | None = STEP_SHA256) -> dict:
    path = Path(path)
    digest = sha256_file(path)
    if expected_sha256 and digest != expected_sha256:
        raise ValueError(f"STEP sha256 mismatch: {digest} != {expected_sha256}")

    text = path.read_text(errors="ignore")
    unit_match = UNIT_RE.search(text)
    unit = unit_match.group(1) if unit_match else None
    scale = _scale_from_unit(unit)

    points: dict[int, np.ndarray] = {}
    for match in POINT_RE.finditer(text):
        nums = [float(part) for part in match.group(2).replace("\n", " ").split(",") if part.strip()]
        if len(nums) == 3:
            points[int(match.group(1))] = np.asarray(nums, dtype=np.float64) * scale

    ends: list[tuple[np.ndarray, np.ndarray]] = []
    missing = 0
    for match in CURVE_RE.finditer(text):
        a = points.get(int(match.group(1)))
        b = points.get(int(match.group(2)))
        if a is None or b is None:
            missing += 1
            continue
        if np.linalg.norm(b - a) < 1.0e-9:
            continue
        ends.append((a, b))

    if not ends:
        raise RuntimeError("no TRIMMED_CURVE segments parsed")

    p1 = np.vstack([seg[0] for seg in ends])
    p2 = np.vstack([seg[1] for seg in ends])
    return {
        "path": str(path),
        "sha256": digest,
        "si_unit_prefix": unit,
        "scale_to_metre": scale,
        "n_points": len(points),
        "n_segments": len(ends),
        "n_missing_endpoints": missing,
        "p1": p1,
        "p2": p2,
    }
