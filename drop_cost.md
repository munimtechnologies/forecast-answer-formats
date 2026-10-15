# What a silently dropped answer costs in the Metaculus tournament

*Part of [forecast-answer-formats](https://github.com/munimtechnologies/forecast-answer-formats).
Made with AI, by MV2 of Munim, Inc. Code Apache-2.0; this text CC BY 4.0.*

The corpora in this repo measure **which** valid LLM answer formats two deployed
forecasting-bot extractors — `mv2-forecaster` and Metaculus's `forecasting-tools`
— silently drop (return nothing) or misread. Each tool drops a different family:
e.g. `forecasting-tools` needs a literal `%` and so drops `Probability: 73`, while
`mv2-forecaster` is label-gated and drops `Probability = 73%` or the same answer
written in prose. This note answers the question that decides whether any of that
matters for money: **given a silent-drop rate `d`, what does it cost in the
tournament prize?**

## The scoring rule

Metaculus's current tournament rule ([*Introducing Simpler, Fairer Tournament
Scores*](https://www.metaculus.com/notebooks/21883/), and the
[Scores FAQ](https://www.metaculus.com/help/scores-faq/)):

- Every question gives a **Peer score** = your log score minus the mean log score
  of the other forecasters on that question. It is positive exactly when you beat
  the field.
- Your **Total Score `S`** is the **sum** of your per-question Peer scores. **A
  question you never forecast contributes `0`.**
- Your prize share is proportional to **`S²`** (negative totals win nothing; a
  prize under **$50** is not paid).

That `sum-then-square` shape is the whole story.

## The result: a drop costs ~2× its rate

Suppose a bot would earn a positive mean Peer score `μ` on each of `N` questions it
genuinely forecasts, so `S = N·μ`. Now a fraction `d` of its answers are silently
dropped — the extractor returns nothing, the bot posts no forecast, and each of
those questions becomes a `0` in the sum. The surviving total is `(1−d)·N·μ`, so
the prize, proportional to `S²`, is multiplied by

> **payout factor = (1 − d)²**

For small `d` the loss `1 − (1−d)²` is approximately `2d`:

| silent-drop rate `d` | payout factor `(1−d)²` | prize lost |
|---:|---:|---:|
| 5%  | 0.9025 | **9.75%** |
| 10% | 0.8100 | **19.0%** |
| 15% | 0.7225 | **27.8%** |
| 20% | 0.6400 | **36.0%** |
| 30% | 0.4900 | **51.0%** |

A silent drop is **about twice as expensive as its raw rate**, purely because the
tournament squares the sum. And it compounds with the $50 floor: an entry whose
full prize is near the threshold can be pushed under it by a modest drop rate and
paid **nothing at all** (`test_drop_cost.py::FloorTests` works an example where a
$60 prize becomes $0 after a 30% drop).

This also sharpens a point other bot authors have noted in passing — that an
unforecast question is "a zero inside that sum"
([Oishi1029](https://github.com/Oishi1029/metaculus-forecasting-bot),
[metac-bot-template #5](https://github.com/jeremynz/metac-bot-template/pull/5)):
the cost is not linear, it is **convex**, and a format family your extractor drops
entirely (which the corpora here identify) is a first-order risk to the prize, not
a cosmetic bug.

## Why `(1−d)²` and not something messier

The law is exact when **one bot's drop does not materially change the pool's
denominator** — true for any non-dominant entrant, since the denominator is the
sum of `S²` over *all* entrants. `drop_cost.py::simulate_share_ratio` checks this
with a Monte Carlo: a target bot with a small mean advantage `μ` inside a pool of
~300 forecasters, a random fraction `d` of its answers zeroed, averaged over 500
trials. The simulated `share(d)/share(0)` tracks `(1−d)²` to within a few percent
for `d` ∈ {10%, 20%, 30%} (`test_drop_cost.py::MonteCarloTests`).

## Honest limits

- **`d` is a scenario, not a measured rate.** The corpora in this repo are
  *designed probes* of format families, not a frequency sample of how often a real
  model emits each format. Use `payout_factor_table` to price a drop rate you
  estimate from your own run logs.
- **Random vs. correlated drops.** The law assumes dropped questions are
  representative. If drops are correlated with format *and* a model favours that
  format on, say, numeric questions, the dropped set is not representative and the
  cost can be larger or smaller than `(1−d)²` — an extension worth measuring on
  real logs.
- **Drops vs. misreads.** This note prices *drops* (peer → 0). A silent **misread**
  (the extractor returns a *wrong* number, e.g. `2 million` parsed as `2.0`) posts
  a confident bad forecast and can earn a large **negative** peer score — plausibly
  worse than a drop. Pricing misreads needs the per-question distribution and is
  left for future work.
- Peer scores vary per question; the model uses a mean advantage `μ`. Metaculus
  reports a scaled log score, but peer *differences* are invariant to a shared
  positive scale, so the share ratios here are unaffected.

## Prior art

Metaculus publishes the scoring rule, and bot authors know unforecast questions
score zero; several templates now log parse failures instead of dropping them.
What is new here is **connecting a format-specific silent-drop rate to the
tournament's square-of-sum payout** to show the cost is convex (`≈ 2d`), tying it
to the companion corpora that identify *which* formats each deployed extractor
drops, with a reproducible, test-gated model anyone can run against their own
estimated drop rate.

## Reproduce

```
python drop_cost.py            # prints the table + Monte Carlo column
python -m unittest -v test_drop_cost.py
```

No dependencies beyond the Python standard library.
