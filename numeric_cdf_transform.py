"""
Characterization of forecasting-tools' numeric nominal<->CDF location transform.

`forecasting-tools` (Metaculus's official AI forecasting framework) maps a real
nominal answer (e.g. $17k) to a CDF location in [0, 1] before submission, and back.
The pair lives in forecasting_tools/data_models/numeric_report.py as
`_nominal_location_to_cdf_location` (forward) and
`_cdf_location_to_nominal_location` (inverse). Source quoted in xtool_numeric_cdf.md.

This module re-implements both in pure stdlib `math` (the library uses numpy; for
positive reals np.log == math.log). A log-scaled question uses a zero_point z that
lies OUTSIDE [lower_bound, upper_bound]: z < lower_bound (increasing) or
z > upper_bound (decreasing). z is a vertical asymptote of the transform; nominal
values on the far side of z have no real image, which the library yields as NaN
(np.log of a non-positive number). We model that with `float('nan')`.

Facts proven in xtool_numeric_cdf.md and checked in the test file:
  1. forward_library == forward_identity on the valid domain, BOTH log branches.
  2. inverse(forward(v)) == v exactly (round trip), both branches, any zero_point.
  3. Unified identity:  L(v) = (ln|v-z| - ln|a-z|) / (ln|b-z| - ln|a-z|).
  4. dL/dv = 1 / ((v - z) * ln r),  r = (b - z)/(a - z):  log-scaling coarsens CDF
     resolution toward high v when z < lower_bound, but SHARPENS it toward high v
     when z > upper_bound -- the two branches place resolution oppositely.
  5. Edge asymmetry: at exactly v == z the library nudges `nominal += 1e-10`. That
     moves toward the valid side for an increasing question (-> large finite
     extrapolation) but away from it for a decreasing one (-> NaN). A sign-aware
     nudge would make both branches extrapolate. Not reported upstream as of
     2026-10-17 (issues #211, #212 cover other numeric paths).

Made with AI, by MV2 of Munim, Inc.  Apache-2.0.
"""

from math import log, nan


def _deriv_ratio(a: float, b: float, z: float) -> float:
    """r = deriv_ratio, exactly as the library computes it."""
    return (b - z) / (a - z)


def forward_library(v: float, a: float, b: float, z: float | None) -> float:
    """Nominal -> CDF location, transcribed from the library (np.log -> math.log).

    a = lower_bound (range_min), b = upper_bound (range_max), z = zero_point
    (None for a linearly scaled question). Returns NaN where the library's np.log
    would (inner argument <= 0, i.e. beyond the asymptote z).
    """
    if z is None:
        return (v - a) / (b - a)
    r = _deriv_ratio(a, b, z)
    if v == z:
        # library adds a small epsilon so the inner log is not log(0)
        v = v + 1e-10
    arg = (v - a) * (r - 1) + (b - a)
    if arg <= 0:
        return nan
    return (log(arg) - log(b - a)) / log(r)


def forward_identity(v: float, a: float, b: float, z: float | None) -> float:
    """The same map in the simplified closed form, valid on the transform's domain.

    For z < a (increasing) each |.| argument equals its signed value; for z > b
    (decreasing) the absolute values flip all three signs consistently, so this one
    formula reproduces the library on the valid side of the asymptote. Beyond the
    asymptote it returns NaN to match forward_library.
    """
    if z is None:
        return (v - a) / (b - a)
    if v == z:
        v = v + 1e-10
    if (z < a and v <= z) or (z > b and v >= z):
        return nan  # far side of the asymptote: no real image
    return (log(abs(v - z)) - log(abs(a - z))) / (log(abs(b - z)) - log(abs(a - z)))


def inverse(cdf_location: float, a: float, b: float, z: float | None) -> float:
    """CDF location -> nominal, transcribed from the library inverse."""
    if z is None:
        return a + (b - a) * cdf_location
    r = _deriv_ratio(a, b, z)
    return a + (b - a) * (r ** cdf_location - 1) / (r - 1)


def dL_dv(v: float, a: float, b: float, z: float | None) -> float:
    """Analytic derivative of the forward transform on its valid domain.

    Linear branch: constant 1/(b - a).
    Log branch: 1 / ((v - z) * ln r). Both factors share sign, so it is always
    positive (L is monotone increasing); its magnitude shrinks with v when z < a
    and grows with v when z > b.
    """
    if z is None:
        return 1.0 / (b - a)
    r = _deriv_ratio(a, b, z)
    return 1.0 / ((v - z) * log(r))
