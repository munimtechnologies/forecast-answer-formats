# The cost of a silent *misread* in a square-of-sum tournament

*Made with AI, by MV2 of Munim, Inc. Part of
[forecast-answer-formats](https://github.com/munimtechnologies/forecast-answer-formats).
Apache-2.0 (code) / CC BY 4.0 (text).*

[`drop_cost.py`](drop_cost.py) priced the first way a forecasting-bot extractor
fails: a **silent drop**, where it returns nothing and the question contributes a
0 to the Total Score. This note prices the second, worse, failure this repo's
corpora also document: a **misread**, where the extractor returns a number that
was never the model's forecast — a base rate it read in passing, a figure from the
reasoning, the wrong one of several percentages — so the bot posts a *confident
wrong* forecast and earns a large **negative** peer score on that question.

The binary corpus already shows this is real, not hypothetical:
`forecasting-tools` takes the last `%`-value anywhere in the text, so a labeled
"...a 5% base rate..." in the reasoning becomes the posted forecast. That is a
misread, and this note is what it costs.

## Setup (same scoring rule as `drop_cost`)

Metaculus's tournament Total Score `S` is the **sum** of per-question peer scores;
an unforecast question is a 0; the prize share is proportional to `max(S, 0)**2`;
negative totals win nothing and prizes under $50 are not paid
([Introducing Simpler, Fairer Tournament Scores](https://www.metaculus.com/notebooks/)).
A question's peer score is *my* log score minus the *mean* log score of the field,
so it is positive exactly when I beat the field.

Let a bot forecast `N` questions and earn a mean peer edge `mu > 0` on each one it
reads correctly. Define the **misread penalty** `L > 0` as the magnitude of the
negative peer score of a confident wrong forecast, and

```
rho = L / mu      (penalty-to-edge ratio)
```

## The law

- A **drop** turns a `+mu` into `0`: it costs `mu` of Total Score.
- A **misread** turns a `+mu` into `-L`: it costs `mu + L = mu*(1 + rho)`.

So, **per event, a misread is `(1 + rho)` times as costly to the Total Score as a
drop.** If a fraction `m` of answers are misread (and the rest earn `+mu`),

```
S = N*mu * (1 - m*(1 + rho))
```

A misread rate `m` therefore behaves like an **effective drop rate** `m*(1 + rho)`,
and (for a non-dominant bot, where its own score does not move the pool's
denominator) the prize factor is

```
prize factor = ( max(0, 1 - m*(1 + rho)) )**2
```

Two things a pure drop never does:

1. **A few misreads can erase many good forecasts.** `rho` is typically *several*,
   because the log score punishes a confident wrong answer far harder than it
   rewards one good answer.
2. **The entry can be zeroed, not just shrunk.** Once `m` exceeds the **zeroing
   rate** `1/(1 + rho)`, the Total Score is `<= 0` and the prize is `0` — the entry
   wins nothing. A drop only reaches a 0 prize in the limit `d -> 1`.

## Worked scenario (nothing tuned)

A binary question resolves **YES**. The field forecasts `0.60`; the bot's good
forecast would be `0.90`; its extractor instead reads a labeled **5% base rate**
(`0.05`) as the forecast. From the log/peer definitions alone:

| quantity | value |
|---|---|
| per-question edge `mu` = ln0.9 − ln0.6 | **0.4055** |
| misread penalty `L` = −(ln0.05 − ln0.6) | **2.4849** |
| ratio `rho = L/mu` | **6.13** |
| one misread costs as much as `1+rho` drops | **≈ 7.1 drops** |
| zeroing misread rate `1/(1+rho)` | **≈ 14.0%** |

So on this question **one misread erases about seven dropped answers' worth of
Total Score**, and a bot that misreads this way on roughly **1 in 7** of its
questions scores zero overall — regardless of how well it forecasts the rest.

## Prize factor by misread rate (`rho = 3`)

| misread rate `m` | effective drop `m(1+rho)` | prize factor | loss |
|---|---|---|---|
| 2% | 0.08 | 0.846 | 15% |
| 5% | 0.20 | 0.640 | 36% |
| 10% | 0.40 | 0.360 | 64% |
| 20% | 0.80 | 0.040 | 96% |
| 30% | 1.20 | **0.000** | **100%** |

Compare `drop_cost`'s table: a 10% *drop* rate keeps 0.81 of the prize; a 10%
*misread* rate at `rho = 3` keeps 0.36. The reproduction (`misread_cost.py
_demo()`) prints this table beside a Monte Carlo column that tracks it.

## Reproduce / verify

`test_misread_cost.py` recomputes every number offline (pure stdlib,
deterministic): the negative peer of a confident wrong forecast, `rho` for the
worked scenario, the `(max(0, 1 - m(1+rho)))**2` factor and its clamp to 0 past
the zeroing rate, the "misread strictly worse than a drop of the same rate"
inequality, and a Monte Carlo over a 300-bot pool confirming a non-dominant bot's
prize share scales with the factor. The publish lane runs it before committing.

## Honest limits

- The law is exact for the sum-then-square rule only for a **non-dominant** entrant
  (one whose score does not materially change the denominator); the Monte Carlo
  checks that regime.
- `rho` is a **scenario, not a measured frequency**: it depends on how confident
  and how wrong the misread is and on the field's forecast. Different misreads
  (e.g. reading `2 million` as `2.0` on a numeric question) give different `L`;
  the method is the same, the number is not.
- Misreads may be **correlated with a format family** (this repo's corpora show
  *which* families each tool misreads) rather than hitting random questions.
- This prices binary misreads via the binary log score; numeric/MC peer scores use
  the same sum-then-square tournament rule, so the `(1+rho)` structure carries over
  with a type-appropriate `L`.

## Prior art

Metaculus publishes the scoring rule, and bot authors note that a drop "is a zero."
`drop_cost.py` (this repo) priced that zero as a convex `(1-d)**2` loss. No prior
work we can find prices a **misread** — a confident *wrong* forecast injected by
the extractor — as a negative peer score, derives that a misread rate `m` acts as
an effective drop rate `m*(1+rho)`, or identifies the `1/(1+rho)` rate at which
extractor misreads zero a tournament entry outright.
