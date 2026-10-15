"""
Offline tests for drop_cost.py. Pure stdlib, deterministic (fixed RNG seed).
Made with AI, by MV2 of Munim, Inc. Apache-2.0.

These assert the paper's claims directly:
  * the log/peer/total/share building blocks are correct on hand-worked inputs;
  * the analytic prize factor from a silent-drop rate d is exactly (1-d)**2;
  * silent drops are convex-costly: the prize loss 1-(1-d)**2 strictly exceeds d;
  * a Monte Carlo over a realistic pool confirms a non-dominant bot's prize share
    scales as (1-d)**2;
  * the $50 floor zeros a near-threshold payout.
"""

import math
import unittest

import drop_cost as dc


class BuildingBlockTests(unittest.TestCase):
    def test_log_score_perfect_and_wrong(self):
        self.assertAlmostEqual(dc.log_score(1.0, 1), 0.0, places=6)
        self.assertAlmostEqual(dc.log_score(0.0, 0), 0.0, places=6)
        # log score is always <= 0 and worse (more negative) for a worse forecast
        self.assertLess(dc.log_score(0.1, 1), dc.log_score(0.9, 1))

    def test_log_score_is_bounded_not_infinite(self):
        # 0 on the realized outcome must be clamped, not -inf
        self.assertTrue(math.isfinite(dc.log_score(0.0, 1)))
        self.assertTrue(math.isfinite(dc.log_score(1.0, 0)))

    def test_log_score_rejects_bad_outcome(self):
        with self.assertRaises(ValueError):
            dc.log_score(0.5, 2)

    def test_peer_score_sign(self):
        # outcome happened (1). Beating a field that forecast 0.5 with 0.9 -> positive.
        self.assertGreater(dc.peer_score(0.9, [0.5, 0.5], 1), 0.0)
        # under-forecasting the field -> negative.
        self.assertLess(dc.peer_score(0.3, [0.5, 0.5], 1), 0.0)
        # no field -> 0
        self.assertEqual(dc.peer_score(0.9, [], 1), 0.0)

    def test_peer_score_value(self):
        # my log score minus mean field log score
        expected = dc.log_score(0.8, 1) - (
            (dc.log_score(0.6, 1) + dc.log_score(0.4, 1)) / 2
        )
        self.assertAlmostEqual(dc.peer_score(0.8, [0.6, 0.4], 1), expected, places=9)

    def test_total_score_and_zeros(self):
        # an unforecast question contributes 0: omitting it or passing 0.0 match
        self.assertAlmostEqual(dc.total_score([0.3, -0.1, 0.2]), 0.4, places=9)
        self.assertAlmostEqual(
            dc.total_score([0.3, 0.0, -0.1, 0.2]),
            dc.total_score([0.3, -0.1, 0.2]),
            places=9,
        )

    def test_prize_share_hand_worked(self):
        # three entrants, totals 2, 1, 1 -> shares 4/6, 1/6, 1/6
        self.assertAlmostEqual(dc.prize_share(2.0, [2.0, 1.0, 1.0]), 4.0 / 6.0, places=9)
        self.assertAlmostEqual(dc.prize_share(1.0, [2.0, 1.0, 1.0]), 1.0 / 6.0, places=9)

    def test_prize_share_excludes_negatives(self):
        # a negative total wins nothing and is not in the denominator
        self.assertEqual(dc.prize_share(-3.0, [2.0, -3.0]), 0.0)
        self.assertAlmostEqual(dc.prize_share(2.0, [2.0, -3.0]), 1.0, places=9)

    def test_prize_share_empty_pool(self):
        self.assertEqual(dc.prize_share(0.0, [0.0, 0.0]), 0.0)


class AnalyticLawTests(unittest.TestCase):
    def test_payout_factor_is_square(self):
        for d in (0.0, 0.05, 0.1, 0.2, 0.3, 0.5, 1.0):
            self.assertAlmostEqual(
                dc.expected_payout_factor(d), (1.0 - d) ** 2, places=12
            )

    def test_payout_factor_known_points(self):
        self.assertAlmostEqual(dc.expected_payout_factor(0.10), 0.81, places=12)
        self.assertAlmostEqual(dc.expected_payout_factor(0.30), 0.49, places=12)

    def test_loss_is_convex_exceeds_rate(self):
        # the headline: a silent-drop rate d loses MORE than d of the prize
        for d in (0.01, 0.05, 0.1, 0.2, 0.3, 0.4):
            self.assertGreater(dc.payout_loss(d), d)
        # and for small d the loss is close to 2d
        self.assertAlmostEqual(dc.payout_loss(0.01), 0.0199, places=6)

    def test_factor_rejects_out_of_range(self):
        with self.assertRaises(ValueError):
            dc.expected_payout_factor(1.5)
        with self.assertRaises(ValueError):
            dc.expected_payout_factor(-0.1)

    def test_table_shape(self):
        tbl = dc.payout_factor_table()
        self.assertIn(0.10, tbl)
        self.assertAlmostEqual(tbl[0.10]["payout_factor"], 0.81, places=9)
        self.assertAlmostEqual(tbl[0.10]["loss"], 0.19, places=9)


class FloorTests(unittest.TestCase):
    def test_near_threshold_entry_zeroed(self):
        # pool $50,000, share 0.0012 -> $60 paid; a 20% drop -> share ~0.0012*0.64
        pool = 50_000.0
        paid_full = dc.paid_after_floor(pool, 0.0012)
        self.assertAlmostEqual(paid_full, 60.0, places=6)
        # after a 30% drop the share scales by (1-0.3)**2 = 0.49 -> $29.4 -> below $50 -> $0
        dropped_share = 0.0012 * dc.expected_payout_factor(0.30)
        self.assertEqual(dc.paid_after_floor(pool, dropped_share), 0.0)

    def test_comfortable_entry_still_paid(self):
        self.assertGreater(dc.paid_after_floor(50_000.0, 0.02), 50.0)


class MonteCarloTests(unittest.TestCase):
    def test_share_ratio_tracks_square_law(self):
        # a non-dominant bot's prize share should scale ~ (1-d)**2
        for d in (0.10, 0.20, 0.30):
            ratio = dc.simulate_share_ratio(d, seed=1)
            self.assertAlmostEqual(
                ratio, dc.expected_payout_factor(d), delta=0.03,
                msg=f"d={d}: MC ratio {ratio:.4f} vs (1-d)^2 {(1-d)**2:.4f}",
            )

    def test_share_ratio_shows_convex_loss(self):
        # the simulated loss must clearly exceed the linear rate for a real d
        ratio = dc.simulate_share_ratio(0.20, seed=2)
        self.assertLess(ratio, 1.0 - 0.20)  # loss > 20%

    def test_no_drop_ratio_is_one(self):
        self.assertAlmostEqual(dc.simulate_share_ratio(0.0, seed=3), 1.0, places=6)


if __name__ == "__main__":
    unittest.main(verbosity=2)
