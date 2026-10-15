"""
Offline tests for combined_cost.py. Pure stdlib, deterministic (fixed RNG seed).
Made with AI, by MV2 of Munim, Inc. Apache-2.0.

These assert the combined model's claims directly:
  * drops and misreads add one effective drop rate d + m*(1+rho);
  * the prize factor is (max(0, 1 - d - m*(1+rho)))**2, clamped to 0 past zeroing;
  * it reduces EXACTLY to drop_cost (m=0) and to misread_cost (d=0);
  * adding a misread to a drop (or vice versa) is strictly worse;
  * for a fixed drop rate d the zeroing misread rate is (1-d)/(1+rho);
  * a tool's corpus tally maps to the expected drop/misread rates and factor;
  * a Monte Carlo over a realistic pool mixing both failure modes tracks the law.
"""

import unittest

import drop_cost as dc
import misread_cost as mc
import combined_cost as cc


class EffectiveRateTests(unittest.TestCase):
    def test_effective_rate_formula(self):
        self.assertAlmostEqual(cc.combined_effective_drop_rate(0.15, 0.10, 3.0), 0.55, places=12)
        self.assertAlmostEqual(cc.combined_effective_drop_rate(0.10, 0.05, 3.0), 0.30, places=12)

    def test_effective_rate_guards(self):
        with self.assertRaises(ValueError):
            cc.combined_effective_drop_rate(0.6, 0.6, 3.0)   # d+m > 1
        with self.assertRaises(ValueError):
            cc.combined_effective_drop_rate(-0.1, 0.1, 3.0)
        with self.assertRaises(ValueError):
            cc.combined_effective_drop_rate(0.1, 0.1, -0.1)


class LawTests(unittest.TestCase):
    def test_factor_matches_square_of_core(self):
        for d, m, rho in ((0.15, 0.10, 3.0), (0.10, 0.05, 6.0), (0.05, 0.02, 2.0)):
            self.assertAlmostEqual(
                cc.combined_payout_factor(d, m, rho),
                (1.0 - d - m * (1.0 + rho)) ** 2,
                places=12,
            )

    def test_clamped_to_zero_past_zeroing(self):
        # d=0.20, m=0.25, rho=3 -> eff 1.20 >= 1 -> prize 0 (not negative-squared)
        self.assertEqual(cc.combined_payout_factor(0.20, 0.25, 3.0), 0.0)

    def test_reduces_to_drop_cost_when_no_misread(self):
        for d in (0.0, 0.05, 0.10, 0.20, 0.30):
            for rho in (0.0, 3.0, 6.0):
                self.assertAlmostEqual(
                    cc.combined_payout_factor(d, 0.0, rho),
                    dc.expected_payout_factor(d),
                    places=12,
                )

    def test_reduces_to_misread_cost_when_no_drop(self):
        for m in (0.0, 0.02, 0.05, 0.10, 0.20):
            for rho in (0.5, 3.0, 6.0):
                self.assertAlmostEqual(
                    cc.combined_payout_factor(0.0, m, rho),
                    mc.misread_payout_factor(m, rho),
                    places=12,
                )

    def test_adding_a_failure_mode_is_strictly_worse(self):
        for d, m, rho in ((0.10, 0.05, 3.0), (0.05, 0.10, 6.0), (0.15, 0.02, 2.0)):
            both = cc.combined_payout_factor(d, m, rho)
            self.assertLess(both, dc.expected_payout_factor(d))        # vs drop-only
            self.assertLess(both, mc.misread_payout_factor(m, rho))    # vs misread-only

    def test_payout_loss_complements_factor(self):
        for d, m, rho in ((0.10, 0.05, 3.0), (0.0, 0.0, 3.0)):
            self.assertAlmostEqual(
                cc.combined_payout_loss(d, m, rho),
                1.0 - cc.combined_payout_factor(d, m, rho),
                places=12,
            )

    def test_no_error_keeps_full_prize(self):
        self.assertEqual(cc.combined_payout_factor(0.0, 0.0, 3.0), 1.0)


class ZeroingTests(unittest.TestCase):
    def test_zeroing_misread_given_drop(self):
        # d=0.10, rho=3 -> (1-0.10)/(1+3) = 0.225; at d=0 it is 1/(1+rho)
        self.assertAlmostEqual(cc.zeroing_misread_rate_given_drop(0.10, 3.0), 0.225, places=12)
        self.assertAlmostEqual(
            cc.zeroing_misread_rate_given_drop(0.0, 3.0),
            mc.zeroing_misread_rate(3.0),
            places=12,
        )
        # at that misread rate the combined factor is ~0
        z = cc.zeroing_misread_rate_given_drop(0.10, 3.0)
        self.assertAlmostEqual(cc.combined_payout_factor(0.10, z, 3.0), 0.0, places=9)
        self.assertGreater(cc.combined_payout_factor(0.10, z * 0.9, 3.0), 0.0)

    def test_zeroing_guards(self):
        with self.assertRaises(ValueError):
            cc.zeroing_misread_rate_given_drop(1.5, 3.0)
        with self.assertRaises(ValueError):
            cc.zeroing_misread_rate_given_drop(0.1, -1.0)


class CorpusTallyTests(unittest.TestCase):
    def test_forecasting_tools_binary_tally(self):
        # forecasting-tools binary leg: 13 correct / 3 miss / 2 false_pos / 2 reject
        r = cc.from_corpus_tally(13, 3, 2, 2, 3.0)
        self.assertEqual(r["total"], 20.0)
        self.assertAlmostEqual(r["drop_rate"], 0.15, places=12)
        self.assertAlmostEqual(r["misread_rate"], 0.10, places=12)
        self.assertAlmostEqual(r["effective_drop_rate"], 0.55, places=12)
        self.assertAlmostEqual(r["payout_factor"], 0.2025, places=12)
        self.assertAlmostEqual(r["payout_loss"], 0.7975, places=12)

    def test_mv2_binary_tally_no_misread(self):
        # mv2-forecaster binary leg: 14 / 2 / 0 / 4 -> pure drop, factor (1-0.10)**2
        r = cc.from_corpus_tally(14, 2, 0, 4, 3.0)
        self.assertAlmostEqual(r["drop_rate"], 0.10, places=12)
        self.assertEqual(r["misread_rate"], 0.0)
        self.assertAlmostEqual(r["payout_factor"], 0.81, places=12)

    def test_tally_guards(self):
        with self.assertRaises(ValueError):
            cc.from_corpus_tally(0, 0, 0, 0, 3.0)
        with self.assertRaises(ValueError):
            cc.from_corpus_tally(-1, 0, 0, 0, 3.0)


class MonteCarloTests(unittest.TestCase):
    def test_share_ratio_tracks_law(self):
        rho = 3.0
        for d, m in ((0.10, 0.05), (0.05, 0.10), (0.10, 0.10)):
            ratio = cc.simulate_combined_share_ratio(d, m, rho, seed=1)
            self.assertAlmostEqual(
                ratio, cc.combined_payout_factor(d, m, rho), delta=0.05,
                msg=f"d={d}, m={m}: MC {ratio:.4f} vs factor "
                    f"{cc.combined_payout_factor(d, m, rho):.4f}",
            )

    def test_no_error_ratio_is_one(self):
        self.assertAlmostEqual(
            cc.simulate_combined_share_ratio(0.0, 0.0, 3.0, seed=3), 1.0, places=6
        )

    def test_past_zeroing_share_collapses(self):
        ratio = cc.simulate_combined_share_ratio(0.20, 0.25, 3.0, seed=2)
        self.assertLess(ratio, 0.05)


if __name__ == "__main__":
    unittest.main(verbosity=2)
