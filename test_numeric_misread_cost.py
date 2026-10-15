"""
Offline, dependency-free tests for numeric_misread_cost.py.

Confirm the analytic numeric-misread law (loss 0.5*z**2, effective drops
z**2/(2*mu), break-even displacement sqrt(2*mu), prize factor (1-d-m*k)**2) and
that a Monte Carlo over calibrated outcomes and a realistic non-dominant pool
reproduces both the 0.5*z**2 loss and the prize factor.

Imports only numeric_misread_cost + stdlib, so the publish-lane test runs it in a
temp dir holding just these two files. Made with AI, by MV2 of Munim, Inc.
Apache-2.0.
"""

import math
import unittest

import numeric_misread_cost as nmc


class TestLawExact(unittest.TestCase):
    def test_loss_is_half_z_squared(self):
        for z in (0.0, 0.2, 0.5, 1.0, 2.0, -1.5):
            self.assertAlmostEqual(nmc.numeric_misread_loss(z), 0.5 * z * z, places=12)

    def test_loss_symmetric_in_sign(self):
        self.assertAlmostEqual(
            nmc.numeric_misread_loss(1.3), nmc.numeric_misread_loss(-1.3), places=12
        )

    def test_gaussian_log_score_peaks_at_center(self):
        # Density is maximal at the centre; any displacement lowers the log score.
        at_center = nmc.gaussian_log_score(0.0, 1.0, 0.0)
        off = nmc.gaussian_log_score(0.0, 1.0, 1.0)
        self.assertGreater(at_center, off)
        # The gap equals 0.5*z**2 for z = 1 sigma.
        self.assertAlmostEqual(at_center - off, 0.5, places=12)

    def test_effective_drops(self):
        self.assertAlmostEqual(nmc.effective_drops_per_misread(2.0, 0.02), 100.0, places=9)
        self.assertAlmostEqual(nmc.effective_drops_per_misread(0.5, 0.05), 2.5, places=9)

    def test_break_even_is_sqrt_2mu_and_zeroes_peer(self):
        for mu in (0.02, 0.05, 0.1):
            zstar = nmc.break_even_displacement(mu)
            self.assertAlmostEqual(zstar, math.sqrt(2.0 * mu), places=12)
            # At z*, the misread peer is exactly 0 -- same as a drop.
            self.assertAlmostEqual(nmc.numeric_misread_peer(mu, zstar), 0.0, places=12)
            # Just beyond z*, the misread is worse than a drop (peer < 0).
            self.assertLess(nmc.numeric_misread_peer(mu, zstar * 1.01), 0.0)

    def test_break_even_is_small_for_small_edge(self):
        # Tournament edges are small, so the break-even displacement is a small
        # fraction of a sigma: a headline, non-obvious consequence.
        self.assertLess(nmc.break_even_displacement(0.05), 0.33)

    def test_factor_reduces_and_monotone(self):
        mu = 0.05
        # m = 0 -> no loss.
        self.assertAlmostEqual(nmc.numeric_misread_factor(0.0, 1.0, mu), 1.0, places=12)
        # combined reduces to drop-only when m = 0: (1-d)**2.
        self.assertAlmostEqual(nmc.combined_factor(0.1, 0.0, 2.0, mu), 0.81, places=12)
        # combined reduces to misread-only when d = 0.
        self.assertAlmostEqual(
            nmc.combined_factor(0.0, 0.05, 0.5, mu),
            nmc.numeric_misread_factor(0.05, 0.5, mu),
            places=12,
        )
        # larger displacement -> smaller factor.
        self.assertGreater(
            nmc.numeric_misread_factor(0.05, 0.5, mu),
            nmc.numeric_misread_factor(0.05, 1.0, mu),
        )

    def test_factor_value(self):
        # z=0.5, mu=0.05 -> k=2.5; m=0.05 -> eff drop 0.125; (1-0.125)**2.
        self.assertAlmostEqual(
            nmc.numeric_misread_factor(0.05, 0.5, 0.05), 0.875 ** 2, places=12
        )

    def test_zeroing_rate(self):
        # k = z**2/(2mu); zeroing rate (1-d)/k.
        self.assertAlmostEqual(nmc.zeroing_misread_rate(0.5, 0.05), 1.0 / 2.5, places=12)
        self.assertAlmostEqual(
            nmc.zeroing_misread_rate(0.5, 0.05, drop_rate=0.2), 0.8 / 2.5, places=12
        )
        # At the zeroing rate the factor is 0.
        mz = nmc.zeroing_misread_rate(1.0, 0.05)
        self.assertAlmostEqual(nmc.numeric_misread_factor(mz, 1.0, 0.05), 0.0, places=12)

    def test_unit_misread_is_catastrophic(self):
        sc = nmc.unit_misread_scenario()
        self.assertAlmostEqual(sc["z"], (2.0 - 2.0e6) / 1.0e6, places=9)
        # Tens of dropped answers from one magnitude misread, peer deeply negative.
        self.assertGreater(sc["effective_drops"], 50.0)
        self.assertLess(sc["misread_peer"], 0.0)


class TestMonteCarlo(unittest.TestCase):
    def test_mc_recovers_half_z_squared(self):
        for z in (0.5, 1.0, 2.0):
            self.assertAlmostEqual(nmc.simulate_loss(z), 0.5 * z * z, delta=0.03)

    def test_mc_tracks_prize_factor(self):
        # Moderate displacement so the share ratio is away from the zeroing edge.
        mu = 0.05
        analytic = nmc.numeric_misread_factor(0.05, 0.5, mu)
        # sigma_field large enough that the target is clearly non-dominant, and
        # enough questions that the per-trial misread noise is small, so the share
        # ratio tracks the analytic square law (and is well clear of the linear
        # (1 - m*k) ~ 0.875 it would show if the prize were not the square).
        mc = nmc.simulate_share_ratio(
            0.05, 0.5, mu=mu, n_questions=400, sigma_field=0.4
        )
        self.assertAlmostEqual(mc, analytic, delta=0.08)


if __name__ == "__main__":
    unittest.main(verbosity=2)
