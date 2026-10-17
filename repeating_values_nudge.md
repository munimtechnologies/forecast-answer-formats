# A neighbor-collision bug in forecasting-tools' repeated-percentile tie-break

*Made with AI by MV2 of Munim, Inc. Code Apache-2.0; this write-up CC BY 4.0.*

## Summary

Metaculus's official [`forecasting-tools`](https://github.com/Metaculus/forecasting-tools)
requires a numeric forecast's declared percentiles to have a **strictly increasing**
value sequence (a valid CDF). When a bot reports the *same* value for several
percentiles, `NumericDistribution._check_and_update_repeating_values` nudges the
duplicates apart. This note shows, with a faithful stdlib re-implementation and
hand-verifiable tests, that the tie-break itself can **break** strict monotonicity —
reproducing the "Problem 2" symptom of open issue
[#212](https://github.com/Metaculus/forecasting-tools/issues/212)
("percentiles ... must be in strictly increasing order") — and that the open fix
PR [#166](https://github.com/Metaculus/forecasting-tools/pull/166) **widens** the
failing window by ~2500× on this one axis even as it addresses others.

## The released code (verbatim)

From `forecasting_tools/data_models/numeric_report.py`, `main` (fetched 2026-10-17),
the in-bounds branch (each line kept short):

```python
elif value_in_bounds:
    greater_epsilon = 1e-6  # TODO: Figure out why normal epsilon doesn't work.
    modification = (1 - percentile.percentile) * greater_epsilon
    final_percentiles.append(
        Percentile(value=value - modification, percentile=percentile.percentile)
    )
```

Non-duplicate percentiles pass through unchanged; the output keeps the input's
percentile-ascending order (no re-sort, no neighbor check).

## The bug

A repeated in-bounds value `V` is always moved **down**, by at most `1e-6`. A distinct
value `P` that passes through is never moved. So if a distinct `P` sits just below `V`
(`P < V` but `V - P` smaller than the nudge), the nudged duplicate lands **below** `P`,
and the sequence is no longer strictly increasing — the exact error the function exists
to prevent.

**Worked example** (bounds 0–100):

| percentile | input value | released output | note |
|---|---|---|---|
| 0.10 | 50.0000005 − 5e-7 (= 50.0) | 50.0 | distinct, unchanged |
| 0.20 | 50.0000005 | 50.0000005 − 8e-7 = **49.9999997** | repeated, nudged down |
| 0.30 | 50.0000005 | 50.0000005 − 7e-7 = 49.9999998 | repeated, nudged down |

Read top to bottom the values go 50.0 → 49.9999997 → 49.9999998: it **decreases** at
the first step. `validate_percentiles` then raises the strictly-increasing error.

**Collision window (released).** A run of equal in-bounds value `V` whose smallest
percentile is `p0` crosses a preceding distinct `P` iff

```
V - P  <  (1 - p0) * 1e-6      (<= 1e-6)
```

## The open fix, PR #166, widens the window ~2500×

PR #166 ("add more robust solution for `_check_and_update_repeating_values`", open since
2025-12-07) replaces the `(1-p)*1e-6` nudge with a **fixed** downward offset
`0.5 / ((cdf_size or 201) - 1)` = **0.0025** for the default `cdf_size = 201`, keeping
(by the PR author's own in-code note) **no neighbor guard**. Its collision window is
therefore `0.0025`, about **2500×** wider than the released `1e-6`. Modeling that
magnitude: a distinct `P = 50.0` only `0.001` below a repeated `V = 50.001` is crossed
(`50.001 − 0.0025 = 49.9985 < 50.0`), whereas under the released code a `0.001` gap is
perfectly safe. So the same failure class not only survives the proposed fix but
triggers on far more realistic inputs on this axis.

*Scope:* we faithfully re-implement and test the **released** method from its exact
source. For PR #166 we model only the nudge **magnitude** (`0.0025`) and compare windows
arithmetically; we did **not** port the PR's full re-ordering, so the `pr166_*` helpers
are a window model, not a faithful port. A reviewer of #166 would want a neighbor-aware
offset (e.g. a fraction of the gap to the previous distinct value) or a final clamp /
re-sort guaranteeing strict monotonicity.

## Reproduce

`test_repeating_values_nudge.py` recomputes every case offline with the Python standard
library only; each assertion is an ordering or window comparison with margins far above
floating-point noise. No network, no model tokens.

```
python -m unittest -v test_repeating_values_nudge
```

## Prior art and honesty

Issue #212 is **open** and names the strictly-increasing error as an unexplored
workflow failure; PR #166 is **open** and PR #371 (open-bound repeats) is **closed**.
We did not find a public statement of (a) the released code's exact in-bounds
neighbor-collision window `(1-p0)*1e-6`, or (b) that PR #166's fixed `0.0025` offset
widens that window ~2500×. This is a correctness analysis, not an upstream pull request:
we are not opening a competing PR on #166. Values within `~1e-6` (released) or `~0.0025`
(PR #166) of each other but not exactly equal are an edge regime, but a real one —
narrow or near-degenerate numeric forecasts land there, which is precisely when the
tie-break runs.
