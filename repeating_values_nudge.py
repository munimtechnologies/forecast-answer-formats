"""
Repeated-percentile tie-break in forecasting-tools: a neighbor-collision bug.

`forecasting-tools` (Metaculus's official AI-forecasting framework) requires a
strictly increasing CDF. When a bot reports the SAME nominal value for several
percentiles, `NumericDistribution._check_and_update_repeating_values` nudges the
duplicates apart so the value sequence becomes strictly increasing. This module
re-implements that released method in pure stdlib and characterizes a failure
mode it does not guard against, which reproduces open issue #212 ("Problem 2":
"percentiles ... must be in strictly increasing order").

Released source quoted verbatim (forecasting_tools/data_models/numeric_report.py,
main @ fetched 2026-10-17; each line kept under 125 chars) in
repeating_values_nudge.md. The in-bounds branch is the one that matters here:

    greater_epsilon = 1e-6
    modification = (1 - percentile.percentile) * greater_epsilon
    final_percentiles.append(Percentile(value=value - modification, ...))

So an in-bounds repeated value V is always nudged DOWNWARD, by at most 1e-6.
A DISTINCT value that is passed through unchanged is never moved. Therefore, if a
distinct value P sits just below a repeated value V (P < V but V - P < the nudge),
the nudged duplicate lands BELOW P -> the output is no longer strictly increasing.
The function meant to prevent the "strictly increasing" error can itself cause it.

THRESHOLDS (derived, hand-verifiable):
- Released code: a run of equal in-bounds value V whose smallest percentile is p0
  collides with a preceding distinct value P iff  V - P < (1 - p0) * 1e-6
  (<= 1e-6). This is the collision window.
- Open fix PR #166 ("add more robust solution for _check_and_update_repeating_values",
  open since 2025-12-07) replaces the (1-p)*1e-6 nudge with a FIXED downward offset
  0.5 / ((cdf_size or 201) - 1) = 0.0025 for the default cdf_size=201, and (per the
  PR author's own note) keeps NO neighbor guard. Its collision window is thus 0.0025,
  ~2500x WIDER than the released code's for the same inputs: the same failure class
  persists and affects far more inputs on this axis, even while #166 fixes others.

Scope/limits: we faithfully re-implement the RELEASED method (exact source) and test
its behavior. For PR #166 we only model the nudge MAGNITUDE (0.0025) and compare
windows arithmetically -- we have not re-implemented the PR's full reordering, so the
#166 helpers below are labeled as a window model, not a faithful port.

Code: Apache-2.0. Prose/data: CC BY 4.0. Made with AI by MV2 of Munim, Inc.
"""
from __future__ import annotations

from collections import Counter, namedtuple

Percentile = namedtuple("Percentile", ["value", "percentile"])


def check_and_update_repeating_values(percentiles, lower_bound, upper_bound):
    """Faithful stdlib re-implementation of the RELEASED method.

    Mirrors NumericDistribution._check_and_update_repeating_values: duplicates are
    nudged, non-duplicates pass through, and the list order (percentile-ascending
    input) is preserved. No re-sort or neighbor check is performed.
    """
    unique_value_count = Counter(p.value for p in percentiles)
    final_percentiles = []
    for percentile in percentiles:
        value = percentile.value
        count = unique_value_count[value]
        repeated_value = count > 1
        value_in_bounds = lower_bound < value < upper_bound
        value_above_bound = value >= upper_bound
        value_below_bound = value <= lower_bound
        epsilon = 1e-10
        if not repeated_value:
            final_percentiles.append(percentile)
        elif value_in_bounds:
            greater_epsilon = 1e-6
            modification = (1 - percentile.percentile) * greater_epsilon
            final_percentiles.append(
                Percentile(value=value - modification, percentile=percentile.percentile)
            )
        elif value_above_bound:
            modification = epsilon * percentile.percentile
            final_percentiles.append(
                Percentile(value=upper_bound + modification, percentile=percentile.percentile)
            )
        elif value_below_bound:
            modification = epsilon * (1 - percentile.percentile)
            final_percentiles.append(
                Percentile(value=lower_bound - modification, percentile=percentile.percentile)
            )
        else:
            raise ValueError(
                f"Unexpected state: value {value} is repeated {count} times. "
                f"Bound is {lower_bound} and {upper_bound}"
            )
    return final_percentiles


def is_strictly_increasing(percentiles):
    """True iff values are strictly increasing in list order (the validator's rule)."""
    return all(
        percentiles[i].value < percentiles[i + 1].value
        for i in range(len(percentiles) - 1)
    )


def released_collision_window(p0):
    """Max gap (V - P) below a repeated in-bounds value V, with smallest run
    percentile p0, that the RELEASED code will cross. = (1 - p0) * 1e-6."""
    return (1 - p0) * 1e-6


def pr166_collision_window(cdf_size=201):
    """PR #166's fixed downward offset = 0.5 / ((cdf_size or 201) - 1)."""
    return 0.5 / ((cdf_size or 201) - 1)


def pr166_least_value(value, cdf_size=201):
    """Model of PR #166's nudged-down value for a repeated in-bounds value's
    smallest percentile: value - 0.5/((cdf_size or 201)-1). Magnitude model only."""
    return value - pr166_collision_window(cdf_size)
