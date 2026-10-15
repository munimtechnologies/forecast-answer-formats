# SPDX-License-Identifier: Apache-2.0
# Part of forecast-answer-formats, by MV2 of Munim, Inc. Licensed under Apache-2.0.
"""Offline proof that the unified cost law reduces to each shipped cost model.

Self-contained: imports only ``unify_cost`` and the standard library, so it runs
in the publish lane's isolated temp directory with no cross-module import.

Each test recomputes the shipped closed form inline (not by importing the other
cost modules) and asserts the unified law gives the same number.
"""

import math
import unittest

import unify_cost as uc


class TestUnifiedLaw(unittest.TestCase):

    def test_effective_drops_is_loss_over_mu(self):
        for mu in (0.02, 0.05, 0.1, 0.5):
            for loss in (0.0, 0.01, mu, 3 * mu):
                self.assertAlmostEqual(uc.effective_drops(loss, mu), loss / mu, places=12)

    def test_drop_is_k_equals_one(self):
        self.assertEqual(uc.drop_k(), 1.0)
        for mu in (0.02, 0.05, 0.1):
            # a drop forgoes exactly the edge mu
            self.assertAlmostEqual(uc.effective_drops(mu, mu), 1.0, places=12)

    def test_drop_matches_1_minus_d_squared(self):
        # drop_cost.py:  prize factor = (1-d)**2
        for mu in (0.02, 0.05, 0.1):
            for d in (0.0, 0.05, 0.1, 0.3):
                got = uc.prize_factor([(d, mu)], mu)  # drop loss = mu
                self.assertAlmostEqual(got, (1.0 - d) ** 2, places=12)

    def test_binary_misread_k_and_factor(self):
        # misread_cost.py:  k = 1+rho, factor = (max(0,1-m*(1+rho)))**2
        for mu in (0.02, 0.05):
            for rho in (0.0, 1.0, 6.1):
                self.assertAlmostEqual(uc.binary_misread_k(rho), 1.0 + rho, places=12)
                loss = mu * (1.0 + rho)  # L_err = mu + L = mu(1+rho)
                self.assertAlmostEqual(uc.effective_drops(loss, mu), 1.0 + rho, places=9)
                for m in (0.0, 0.05, 0.1):
                    got = uc.prize_factor([(m, loss)], mu)
                    self.assertAlmostEqual(got, (max(0.0, 1.0 - m * (1.0 + rho))) ** 2, places=9)

    def test_binary_misread_zeroing_rate(self):
        # entry zeroed once m > 1/(1+rho)
        rho = 6.1
        mu = 0.05
        m_star = uc.zeroing_rate(mu * (1.0 + rho), mu)
        self.assertAlmostEqual(m_star, 1.0 / (1.0 + rho), places=9)
        # just above m_star the prize is zero
        self.assertEqual(uc.prize_factor([(m_star + 0.01, mu * (1.0 + rho))], mu), 0.0)

    def test_numeric_misread_k_and_breakeven(self):
        # numeric_misread_cost.py:  k = z**2/(2*mu), z* = sqrt(2*mu)
        for mu in (0.02, 0.05, 0.1):
            for z in (0.1, 0.3, 0.5, 2.0):
                self.assertAlmostEqual(uc.numeric_misread_k(z, mu), z * z / (2.0 * mu), places=12)
            z_star = uc.break_even_displacement(mu)
            self.assertAlmostEqual(z_star, math.sqrt(2.0 * mu), places=12)
            # at break-even a numeric misread costs exactly one drop
            self.assertAlmostEqual(uc.numeric_misread_k(z_star, mu), uc.drop_k(), places=12)

    def test_numeric_vs_drop_ordering(self):
        # below z* cheaper than a drop, above z* costlier
        mu = 0.05
        z_star = uc.break_even_displacement(mu)
        self.assertLess(uc.numeric_misread_k(z_star * 0.5, mu), 1.0)
        self.assertGreater(uc.numeric_misread_k(z_star * 2.0, mu), 1.0)

    def test_combined_channels_match_combined_cost(self):
        # combined_cost.py:  factor = (max(0, 1 - d - m*(1+rho)))**2
        mu = 0.02
        rho = 6.1
        for d in (0.0, 0.05):
            for m in (0.0, 0.05):
                got = uc.prize_factor([(d, mu), (m, mu * (1.0 + rho))], mu)
                want = (max(0.0, 1.0 - d - m * (1.0 + rho))) ** 2
                self.assertAlmostEqual(got, want, places=9)

    def test_prize_factor_clamps_at_zero(self):
        mu = 0.05
        rho = 6.1
        # m=0.2 with (1+rho)=7.1 gives 1.42 > 1, so the entry is zeroed
        self.assertEqual(uc.prize_factor([(0.2, mu * (1.0 + rho))], mu), 0.0)

    def test_input_validation(self):
        with self.assertRaises(ValueError):
            uc.effective_drops(0.1, 0.0)
        with self.assertRaises(ValueError):
            uc.effective_drops(-0.1, 0.05)
        with self.assertRaises(ValueError):
            uc.binary_misread_k(-0.5)
        with self.assertRaises(ValueError):
            uc.prize_factor([(-0.1, 0.05)], 0.05)


if __name__ == "__main__":
    unittest.main()
