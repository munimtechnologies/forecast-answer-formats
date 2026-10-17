"""
Deterministic, offline tests for numeric_cdf_transform.

Every expected number is hand-computable (no numpy, no network, no fixtures):

Increasing log branch  a=1, b=1e6, z=0  => r = 1e6:
    L(v) = ln v / ln 1e6, so L(1)=0, L(1000)=0.5, L(1e6)=1; inverse(0.5)=1000.
Decreasing log branch  a=1, b=1e6, z=1000001  => r = 1e-6:
    L(v) = (ln(z-v) - ln 1e6) / (-ln 1e6); L(1)=0, L(999001)=0.5, L(1e6)=1;
    inverse(0.5)=999001 (the 999999 factor cancels exactly).
Linear branch z=None: L(v) = (v-a)/(b-a).

Made with AI, by MV2 of Munim, Inc.  Apache-2.0.
"""

import math
import unittest

import numeric_cdf_transform as t

INC = dict(a=1.0, b=1_000_000.0, z=0.0)          # increasing: z < a, r = 1e6
DEC = dict(a=1.0, b=1_000_000.0, z=1_000_001.0)  # decreasing: z > b, r = 1e-6


class TestEndpointsAndMidpoints(unittest.TestCase):
    def test_increasing_hand_values(self):
        self.assertAlmostEqual(t.forward_library(1.0, **INC), 0.0, places=9)
        self.assertAlmostEqual(t.forward_library(1000.0, **INC), 0.5, places=9)
        self.assertAlmostEqual(t.forward_library(1_000_000.0, **INC), 1.0, places=9)

    def test_decreasing_hand_values(self):
        self.assertAlmostEqual(t.forward_library(1.0, **DEC), 0.0, places=9)
        self.assertAlmostEqual(t.forward_library(999_001.0, **DEC), 0.5, places=9)
        self.assertAlmostEqual(t.forward_library(1_000_000.0, **DEC), 1.0, places=9)

    def test_linear_hand_values(self):
        lin = dict(a=0.0, b=10.0, z=None)
        self.assertAlmostEqual(t.forward_library(0.0, **lin), 0.0, places=12)
        self.assertAlmostEqual(t.forward_library(5.0, **lin), 0.5, places=12)
        self.assertAlmostEqual(t.forward_library(10.0, **lin), 1.0, places=12)


class TestLibraryEqualsIdentity(unittest.TestCase):
    def _grid(self, params):
        a, b = params["a"], params["b"]
        for i in range(1, 20):
            v = a + (b - a) * i / 20.0
            self.assertAlmostEqual(
                t.forward_library(v, **params),
                t.forward_identity(v, **params),
                places=9,
                msg=f"mismatch at v={v} params={params}",
            )

    def test_increasing(self):
        self._grid(INC)

    def test_decreasing(self):
        self._grid(DEC)


class TestRoundTrip(unittest.TestCase):
    def _roundtrip(self, params):
        a, b = params["a"], params["b"]
        for i in range(0, 21):
            v = a + (b - a) * i / 20.0
            L = t.forward_library(v, **params)
            back = t.inverse(L, **params)
            self.assertAlmostEqual(back, v, delta=abs(v) * 1e-9 + 1e-9,
                                   msg=f"round trip failed v={v} params={params}")

    def test_increasing(self):
        self._roundtrip(INC)

    def test_decreasing(self):
        self._roundtrip(DEC)

    def test_linear(self):
        self._roundtrip(dict(a=0.0, b=10.0, z=None))

    def test_inverse_midpoint(self):
        self.assertAlmostEqual(t.inverse(0.5, **INC), 1000.0, delta=1e-4)
        self.assertAlmostEqual(t.inverse(0.5, **DEC), 999_001.0, delta=1e-3)


class TestDerivativeDirection(unittest.TestCase):
    def test_increasing_coarsens_toward_high_v(self):
        # z < a: sensitivity dL/dv shrinks as v grows (coarser resolution high up)
        self.assertGreater(t.dL_dv(10.0, **INC), t.dL_dv(1000.0, **INC))
        self.assertGreater(t.dL_dv(10.0, **INC), 0.0)

    def test_decreasing_sharpens_toward_high_v(self):
        # z > b: sensitivity dL/dv grows as v grows (finer resolution high up)
        self.assertGreater(t.dL_dv(999_001.0, **DEC), t.dL_dv(10.0, **DEC))
        self.assertGreater(t.dL_dv(10.0, **DEC), 0.0)

    def test_linear_is_constant(self):
        lin = dict(a=0.0, b=10.0, z=None)
        self.assertAlmostEqual(t.dL_dv(1.0, **lin), t.dL_dv(9.0, **lin), places=12)
        self.assertAlmostEqual(t.dL_dv(1.0, **lin), 0.1, places=12)


class TestZeroPointEdgeAsymmetry(unittest.TestCase):
    """At exactly v == zero_point the hard-coded +1e-10 nudge is sign-blind:
    it extrapolates to a finite value for an increasing question but yields NaN
    for a decreasing one."""

    def test_increasing_at_zero_point_is_finite(self):
        val = t.forward_library(INC["z"], **INC)  # v == z == 0
        self.assertTrue(math.isfinite(val))
        self.assertLess(val, 0.0)  # below 0: beyond the bounds, as documented

    def test_decreasing_at_zero_point_is_nan(self):
        val = t.forward_library(DEC["z"], **DEC)  # v == z == 1_000_001
        self.assertTrue(math.isnan(val))

    def test_identity_matches_edge_behavior(self):
        self.assertTrue(math.isfinite(t.forward_identity(INC["z"], **INC)))
        self.assertTrue(math.isnan(t.forward_identity(DEC["z"], **DEC)))


if __name__ == "__main__":
    unittest.main(verbosity=2)
