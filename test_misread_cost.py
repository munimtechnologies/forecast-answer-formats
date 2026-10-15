"""
Offline tests for misread_cost.py. Pure stdlib, deterministic (fixed RNG seed).
Made with AI, by MV2 of Munim, Inc. Apache-2.0.

These assert the paper's claims directly:
  * a confident wrong forecast earns a NEGATIVE peer score; its magnitude is L;
  * rho = L/mu for the worked base-rate-misread scenario matches the hand value;
  * per event, a misread costs (1+rho) times a drop; a misread rate m acts like an
    effective drop rate m*(1+rho), giving prize factor (max(0,1-m(1+rho)))**2;
  * a misread is strictly worse than a drop of the same rate (for rho>0);
  * the Total Score hits 0 -- so the prize is 0 -- at the zeroing rate 1/(1+rho);
  * a Monte Carlo over a realistic pool confirms the factor for a non-dominant bot.
"""

import unittest

import drop_cost as dc
import misread_cost as mc


class PenaltyTests(unittest.TestCase):
    def test_confident_wrong_is_negative_peer(self):
        # field 0.6, outcome YES, extractor reads 0.05 -> loses to the field
        self.assertLess(mc.misread_peer(0.05, 0.6, 1), 0.0)
        self.assertGreater(mc.miss_penalty(0.05, 0.6, 1), 0.0)

    def test_penalty_equals_negated_peer(self):
        self.assertAlmostEqual(
            mc.miss_penalty(0.05, 0.6, 1),
            -dc.peer_score(0.05, [0.6], 1),
            places=12,
        )

    def test_rho_hand_worked(self):
        # mu = ln0.9 - ln0.6 = 0.405465; L = -(ln0.05 - ln0.6) = 2.484907
        rho = mc.penalty_to_edge_ratio(0.90, 0.05, 0.60, 1)
        self.assertAlmostEqual(rho, 2.484907 / 0.405465, places=4)
        self.assertAlmostEqual(rho, 6.1285, places=3)

    def test_rho_requires_positive_edge(self):
        # if the "good" forecast does not beat the field, rho is undefined
        with self.assertRaises(ValueError):
            mc.penalty_to_edge_ratio(0.4, 0.05, 0.6, 1)


class LawTests(unittest.TestCase):
    def test_per_event_cost_ratio(self):
        for rho in (0.0, 1.0, 3.0, 6.1285):
            self.assertAlmostEqual(mc.per_event_cost_ratio(rho), 1.0 + rho, places=12)

    def test_effective_drop_rate(self):
        self.assertAlmostEqual(mc.effective_drop_rate(0.10, 3.0), 0.40, places=12)
        self.assertAlmostEqual(mc.effective_drop_rate(0.05, 6.1285), 0.356425, places=6)

    def test_payout_factor_matches_square_of_core(self):
        for m, rho in ((0.05, 3.0), (0.10, 3.0), (0.02, 6.0)):
            self.assertAlmostEqual(
                mc.misread_payout_factor(m, rho),
                (1.0 - m * (1.0 + rho)) ** 2,
                places=12,
            )

    def test_payout_factor_clamped_to_zero_past_zeroing(self):
        # m*(1+rho) > 1 -> Total Score <= 0 -> prize 0, not negative-squared
        self.assertEqual(mc.misread_payout_factor(0.30, 3.0), 0.0)
        self.assertEqual(mc.misread_payout_factor(0.50, 6.0), 0.0)

    def test_misread_strictly_worse_than_drop(self):
        # same rate, rho>0: a misread keeps strictly less of the prize than a drop
        for m in (0.02, 0.05, 0.10):
            for rho in (0.5, 3.0, 6.0):
                self.assertLess(
                    mc.misread_payout_factor(m, rho),
                    dc.expected_payout_factor(m),
                    msg=f"m={m}, rho={rho}",
                )

    def test_zeroing_rate(self):
        for rho in (1.0, 3.0, 6.1285):
            z = mc.zeroing_misread_rate(rho)
            self.assertAlmostEqual(z, 1.0 / (1.0 + rho), places=12)
            # at the zeroing rate the factor is (essentially) 0
            self.assertAlmostEqual(mc.misread_payout_factor(z, rho), 0.0, places=9)
            # just below it the entry still scores positive
            self.assertGreater(mc.misread_payout_factor(z * 0.9, rho), 0.0)

    def test_out_of_range_guards(self):
        with self.assertRaises(ValueError):
            mc.effective_drop_rate(1.5, 3.0)
        with self.assertRaises(ValueError):
            mc.per_event_cost_ratio(-0.1)
        with self.assertRaises(ValueError):
            mc.zeroing_misread_rate(-0.1)


class ScenarioTests(unittest.TestCase):
    def test_base_rate_scenario_numbers(self):
        sc = mc.base_rate_misread_scenario()
        self.assertAlmostEqual(sc["mu"], 0.405465, places=5)
        self.assertAlmostEqual(sc["L"], 2.484907, places=5)
        self.assertAlmostEqual(sc["rho"], 6.1285, places=3)
        # one misread ~ 7 drops; zeroing near 14%
        self.assertAlmostEqual(sc["per_event_vs_drop"], 7.1285, places=3)
        self.assertAlmostEqual(sc["zeroing_misread_rate"], 0.1403, places=3)


class MonteCarloTests(unittest.TestCase):
    def test_share_ratio_tracks_law(self):
        rho = 3.0
        for m in (0.05, 0.10, 0.15):
            ratio = mc.simulate_misread_share_ratio(m, rho, seed=1)
            self.assertAlmostEqual(
                ratio, mc.misread_payout_factor(m, rho), delta=0.04,
                msg=f"m={m}: MC {ratio:.4f} vs factor {mc.misread_payout_factor(m, rho):.4f}",
            )

    def test_no_misread_ratio_is_one(self):
        self.assertAlmostEqual(
            mc.simulate_misread_share_ratio(0.0, 3.0, seed=3), 1.0, places=6
        )

    def test_past_zeroing_share_collapses(self):
        # m well past 1/(1+rho) -> Total Score negative -> share ~ 0
        ratio = mc.simulate_misread_share_ratio(0.30, 3.0, seed=2)
        self.assertLess(ratio, 0.05)


if __name__ == "__main__":
    unittest.main(verbosity=2)
