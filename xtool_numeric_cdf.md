# The numeric nominal&harr;CDF transform in forecasting-tools: exact identity, round-trip, and a zero-point edge case

*Made with AI, by MV2 of Munim, Inc. Code Apache-2.0; this text CC BY 4.0.*

Everything else in this repo studies how deployed forecasting bots **read** an
answer out of model text. This note studies the next stage for *numeric*
questions: how [`forecasting-tools`](https://github.com/Metaculus/forecasting-tools)
(Metaculus's official framework) **converts** a nominal answer (e.g. `$17k`) into a
CDF location in `[0, 1]` before submission, and back. It is a self-contained,
offline characterization &mdash; no GPU, no numpy, no network &mdash; verified by
`test_numeric_cdf_transform.py` with hand-computable values.

## The source (quoted verbatim, `forecasting_tools/data_models/numeric_report.py`, main, 2026-10-17)

Forward, `_nominal_location_to_cdf_location`:

```python
range_max = self.upper_bound
range_min = self.lower_bound
zero_point = self.zero_point
if zero_point is not None:
    deriv_ratio = (range_max - zero_point) / (range_min - zero_point)
    if nominal_value == zero_point:
        nominal_value += 1e-10
    unscaled_location = (
        np.log((nominal_value - range_min) * (deriv_ratio - 1)
               + (range_max - range_min))
        - np.log(range_max - range_min)
    ) / np.log(deriv_ratio)
else:
    unscaled_location = (nominal_value - range_min) / (range_max - range_min)
```

Inverse, `_cdf_location_to_nominal_location` (log branch):

```python
deriv_ratio = (range_max - zero_point) / (range_min - zero_point)
scaled_location = range_min + (range_max - range_min) * (
    deriv_ratio**cdf_location - 1
) / (deriv_ratio - 1)
```

Write `a = lower_bound`, `b = upper_bound`, `z = zero_point`,
`r = deriv_ratio = (b - z)/(a - z)`. A log question requires `z` **outside**
`[a, b]`: `z < a` (increasing) or `z > b` (decreasing).

## 1. The forward map is standard log-interpolation, in one formula for both branches

Expanding the library's inner argument with `r - 1 = (b - a)/(a - z)`:

```
(v - a)(r - 1) + (b - a) = (b - a)(v - z)/(a - z)
```

so the whole forward expression collapses to

```
L(v) = ( ln|v - z| - ln|a - z| ) / ( ln|b - z| - ln|a - z| )
```

The absolute values matter: for `z < a` all three differences are positive and
equal their signed values; for `z > b` all three are negative and the signs cancel
pairwise. **The same closed form therefore covers both the increasing and the
decreasing log branch** &mdash; the latter is exercised here for the first time in
this line of work. `test_numeric_cdf_transform.py` checks `forward_library ==
forward_identity` on a 19-point grid in each branch.

## 2. The round trip is exact (both branches, any zero point)

Let `L = L(v)`. Then `r^L = exp(L&middot;ln r) = [(v-a)(r-1)+(b-a)]/(b-a)`, so

```
(r^L - 1)/(r - 1) = (v - a)/(b - a)   =>   inverse(L) = a + (b-a)(v-a)/(b-a) = v.
```

No step depends on the sign of `r - 1`, so `inverse(forward(v)) = v` holds for `r > 1`
and `0 < r < 1` alike. Verified numerically across both branches, including the
hand values `inverse(0.5) = 1000` (increasing `a=1, b=1e6, z=0`) and
`inverse(0.5) = 999001` (decreasing `a=1, b=1e6, z=1000001`).

## 3. The two log branches place resolution in opposite directions

Differentiating the identity, `dL/dv = 1 / ((v - z) &middot; ln r)`. Both factors share
a sign, so `L` is strictly increasing. The magnitude is `1 / (|v - z| &middot; |ln r|)`:

* **Increasing (`z < a`):** `|v - z|` grows with `v`, so `dL/dv` **shrinks** &mdash;
  CDF resolution is coarsest at the top of the range (the familiar log-scale feel).
* **Decreasing (`z > b`):** `|v - z| = z - v` shrinks as `v` rises, so `dL/dv`
  **grows** &mdash; resolution is *finest* at the top of the range.

So the choice of which side `z` sits on silently decides where a numeric forecast
has the most CDF precision. This is useful to know when designing or debugging a
numeric bot; I did not find it stated anywhere in the project's docs or issues.

## 4. A minor edge case at exactly `v == zero_point`

`z` is a vertical asymptote: nominal values on its far side have no real image, and
both branches correctly return NaN there (np.log of a non-positive number) &mdash;
expected and symmetric, not a defect. But **at exactly `v == z`** the library nudges
`nominal_value += 1e-10` to avoid `log(0)`. That nudge is sign-blind:

* increasing (`z < a`, valid side is `v > z`): `z + 1e-10` lands on the valid side
  &rarr; a large finite (negative) extrapolation, consistent with the docstring's
  "can go below 0 if beyond the bounds";
* decreasing (`z > b`, valid side is `v < z`): `z + 1e-10` lands on the *wrong* side
  &rarr; **NaN**.

A sign-aware nudge (subtract for a decreasing question) would make both branches
extrapolate identically. The trigger is an out-of-range input exactly at the
asymptote, so practical impact is small; I note it only as an honest, reproducible
asymmetry. As of 2026-10-17 it is not covered by the open numeric issues (#211 is
multiple-choice min-probability; #212 is repeated percentile values).

## Scope and honesty

This characterizes the transform; it does not re-run any bot or touch live
Metaculus. Claims 1&ndash;3 are proven algebraically and checked offline with
hand-computable values; claim 4 is a reproduced edge behavior, deliberately not
framed as a high-impact bug. No upstream PR is opened from here.
