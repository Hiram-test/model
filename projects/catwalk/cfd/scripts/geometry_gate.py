"""Apply the accepted drawing-prototype scope and check the geometry review."""
import json
from pathlib import Path


def require_geometry_ready(mesh):
    root = Path(__file__).resolve().parents[1]
    cfg = json.loads((Path(mesh) / 'geometry.json').read_text())
    audit = json.loads((root / cfg.get('geometry_audit', 'geometry/audit_status.json')).read_text())
    allowed = cfg.get('model_status') == 'ENGINEERING_SIMPLIFICATION' and audit.get('engineering_runs_allowed')
    if not allowed and (not audit.get('production_ready') or cfg.get('model_status') != 'VALIDATED_GEOMETRY'):
        raise RuntimeError('Geometry not ready for production CFD: see geometry/audit_status.json and audit_register.csv. '
                           'Current trial geometry is not a validated wind-tunnel model.')
