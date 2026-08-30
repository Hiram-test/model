"""Drawing-faithful passage rule shared by ANSYS CE delete and CCX equation drop.

1225 drawings / report 4.4-4.5:
- |ΔY| >= 15000 mm is a cross-walkway lock. Drop it.
- same-walkway keeps translational hinge (UXYZ), not ROT.
- cable UXYZ and bottom-hoop ALL stay if their Y-span is below the cut.
- no E20/E21 spring stiffness, no back-tune to 0.0996 Hz.
"""

from __future__ import annotations

from dataclasses import dataclass

CROSS_Y_MM = 15000.0


@dataclass(frozen=True)
class ConstraintSpan:
    identity: str
    y_min_mm: float
    y_max_mm: float
    kind: str

    @property
    def dy_mm(self) -> float:
        return abs(self.y_max_mm - self.y_min_mm)

    @property
    def is_cross_walkway(self) -> bool:
        return self.dy_mm >= CROSS_Y_MM


def classify_constraint(span: ConstraintSpan) -> str:
    if span.kind in {"bottom_hoop_all", "toppin", "cable_uxyz"} and not span.is_cross_walkway:
        return "KEEP"
    if span.is_cross_walkway:
        return "DROP_CROSS_Y"
    if span.kind in {"passage_all", "passage_uxyz", "equation"}:
        return "KEEP_SAME_WALKWAY_UXYZ"
    return "KEEP"


def decide_equations(spans: list[ConstraintSpan]) -> dict[str, object]:
    kept = []
    dropped = []
    same = []
    for span in spans:
        action = classify_constraint(span)
        record = {
            "identity": span.identity,
            "kind": span.kind,
            "dy_mm": span.dy_mm,
            "action": action,
        }
        if action == "DROP_CROSS_Y":
            dropped.append(record)
        elif action == "KEEP_SAME_WALKWAY_UXYZ":
            same.append(record)
            kept.append(record)
        else:
            kept.append(record)
    if not dropped:
        raise ValueError("no cross-walkway constraint dropped; refuse to launch")
    return {
        "cut_mm": CROSS_Y_MM,
        "dropped": dropped,
        "same_walkway_uxyz": same,
        "kept": kept,
        "target_access": "NONE",
        "claims": {
            "frequency_reproduced": False,
            "e20_e21_springs": False,
            "back_tuned_to_0_0996": False,
        },
    }
