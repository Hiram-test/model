from __future__ import annotations

import unittest

from c3_draw_passage_policy import CROSS_Y_MM, ConstraintSpan, classify_constraint, decide_equations


class PassagePolicyTests(unittest.TestCase):
    def test_cross_y_dropped(self) -> None:
        span = ConstraintSpan("ce-1", -21400.0, 21400.0, "equation")
        self.assertGreaterEqual(span.dy_mm, CROSS_Y_MM)
        self.assertEqual(classify_constraint(span), "DROP_CROSS_Y")

    def test_same_walkway_kept_as_uxyz(self) -> None:
        span = ConstraintSpan("ce-2", 21400.0, 24860.0, "passage_all")
        self.assertEqual(classify_constraint(span), "KEEP_SAME_WALKWAY_UXYZ")

    def test_cable_and_hoop_kept(self) -> None:
        cable = ConstraintSpan("cable", 21400.0, 21420.0, "cable_uxyz")
        hoop = ConstraintSpan("hoop", 24800.0, 25140.0, "bottom_hoop_all")
        self.assertEqual(classify_constraint(cable), "KEEP")
        self.assertEqual(classify_constraint(hoop), "KEEP")

    def test_refuse_launch_without_drop(self) -> None:
        spans = [ConstraintSpan("only-same", 20000.0, 21000.0, "passage_all")]
        with self.assertRaisesRegex(ValueError, "refuse to launch"):
            decide_equations(spans)

    def test_decision_counts(self) -> None:
        report = decide_equations(
            [
                ConstraintSpan("cross", -21400.0, 21400.0, "equation"),
                ConstraintSpan("same", 21400.0, 22000.0, "passage_all"),
                ConstraintSpan("cable", 0.0, 10.0, "cable_uxyz"),
            ]
        )
        self.assertEqual(len(report["dropped"]), 1)
        self.assertEqual(len(report["same_walkway_uxyz"]), 1)
        self.assertFalse(report["claims"]["e20_e21_springs"])
        self.assertFalse(report["claims"]["back_tuned_to_0_0996"])


if __name__ == "__main__":
    unittest.main()
