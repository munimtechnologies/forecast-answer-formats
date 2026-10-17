"""
Deterministic, token-free tests for repeating_values_nudge.py.

Every assertion is an ordering or a window comparison with margins far above
floating-point noise (ulps near value 50 are ~7e-15, our margins are >=1e-7), so
no exact-decimal equality is relied on where floats are subtracted.

Run: python -m unittest -v test_repeating_values_nudge
"""
import unittest

from repeating_values_nudge import (
    Percentile,
    check_and_update_repeating_values,
    is_strictly_increasing,
    released_collision_window,
    pr166_collision_window,
    pr166_least_value,
)

LOWER, UPPER = 0.0, 100.0


class ReleasedCode(unittest.TestCase):
    def test_passthrough_when_no_repeats(self):
        pcts = [Percentile(10.0, 0.1), Percentile(20.0, 0.2), Percentile(30.0, 0.3)]
        out = check_and_update_repeating_values(pcts, LOWER, UPPER)
        self.assertEqual([p.value for p in out], [10.0, 20.0, 30.0])
        self.assertTrue(is_strictly_increasing(out))

    def test_repeated_run_is_internally_increasing(self):
        # A run of equal in-bounds values, no distinct near-neighbor below.
        pcts = [Percentile(50.0, 0.2), Percentile(50.0, 0.3), Percentile(50.0, 0.4)]
        out = check_and_update_repeating_values(pcts, LOWER, UPPER)
        # released nudge: 50 - (1-p)*1e-6, increasing in p, all strictly below 50.
        self.assertTrue(is_strictly_increasing(out))
        self.assertTrue(all(p.value < 50.0 for p in out))

    def test_distinct_neighbor_far_below_is_safe(self):
        # gap (V - P) = 0.5 >> window (<=1e-6): no crossing.
        pcts = [
            Percentile(49.5, 0.1),            # distinct, passes through
            Percentile(50.0, 0.2),            # repeated
            Percentile(50.0, 0.3),            # repeated
        ]
        out = check_and_update_repeating_values(pcts, LOWER, UPPER)
        self.assertTrue(is_strictly_increasing(out))

    def test_distinct_neighbor_within_window_breaks_monotonicity(self):
        # THE BUG (reproduces issue #212 Problem 2): a distinct value sits
        # 5e-7 below a repeated value, inside the <=1e-6 nudge window.
        # p0 = 0.2 -> window = (1-0.2)*1e-6 = 8e-7 > gap 5e-7 => crossing.
        V = 50.0000005
        P = V - 5e-7                          # 50.0 exactly
        pcts = [
            Percentile(P, 0.1),               # distinct, UNCHANGED
            Percentile(V, 0.2),               # repeated, nudged down 8e-7 -> V-8e-7
            Percentile(V, 0.3),               # repeated, nudged down 7e-7 -> V-7e-7
        ]
        out = check_and_update_repeating_values(pcts, LOWER, UPPER)
        # first repeated output drops below the distinct neighbor P:
        self.assertEqual(out[0].value, P)                 # passthrough, exact
        self.assertLess(out[1].value, out[0].value)       # <-- non-monotonic
        self.assertFalse(is_strictly_increasing(out))     # validator would raise
        # the two repeated points are still internally ordered:
        self.assertLess(out[1].value, out[2].value)

    def test_released_window_formula_predicts_boundary(self):
        # window at p0=0.2 is 8e-7; a gap just under it crosses, just over it is safe.
        w = released_collision_window(0.2)
        self.assertAlmostEqual(w, 8e-7, places=12)
        for gap, expect_break in [(w * 0.5, True), (w * 2.0, False)]:
            V = 50.000001
            P = V - gap
            pcts = [Percentile(P, 0.1), Percentile(V, 0.2), Percentile(V, 0.3)]
            out = check_and_update_repeating_values(pcts, LOWER, UPPER)
            self.assertEqual(is_strictly_increasing(out), not expect_break)


class ProposedFixPR166(unittest.TestCase):
    """Window arithmetic + magnitude model for open PR #166 (see module docstring)."""

    def test_window_is_0p0025_for_default_cdf_size(self):
        self.assertAlmostEqual(pr166_collision_window(201), 0.0025, places=12)

    def test_pr166_window_is_about_2500x_wider_than_released(self):
        released_max = released_collision_window(0.0)   # largest possible = 1e-6
        ratio = pr166_collision_window(201) / released_max
        self.assertGreater(ratio, 2000.0)
        self.assertAlmostEqual(ratio, 2500.0, places=6)

    def test_pr166_model_crosses_neighbor_when_gap_under_window(self):
        # distinct P sits 0.001 below repeated V; 0.001 < 0.0025 window => crossing.
        V, P = 50.001, 50.0
        self.assertLess(pr166_least_value(V, 201), P)    # nudged point below neighbor
        # and a gap above the window is safe:
        V2, P2 = 50.01, 50.0                             # gap 0.01 > 0.0025
        self.assertGreater(pr166_least_value(V2, 201), P2)


if __name__ == "__main__":
    unittest.main()
