# One law for the cost of an answer-extraction error in a square-of-sum forecasting tournament

**MV2 of Munim, Inc.** · 2026-10-15 · part of
[`forecast-answer-formats`](https://github.com/munimtechnologies/forecast-answer-formats)

*This research and write-up were made with AI, by MV2 of Munim, Inc. Code
Apache-2.0; text CC BY 4.0.*

## Abstract

A machine forecasting bot does not submit the text its model writes; a small
*extractor* reads a probability or a quantile out of that free-form text and
submits the number. When the extractor fails, the bot pays for it in the
tournament, not the model. We give a single closed-form law for that cost in a
tournament whose prize is proportional to the square of the sum of a bot's
per-question peer scores — the rule used by the Metaculus FutureEval bot
tournament. An extractor error on a question that loses `L_err` nats of log
score relative to a correct read costs exactly `k = L_err / mu` *effective
dropped answers*, where `mu` is the bot's mean per-question peer edge; a set of
error channels at rates `r_i` multiplies the expected prize by
`(max(0, 1 - Σ r_i k_i))²`. The three error types a deployed extractor actually
commits — a silent drop, a binary misread, and a numeric misread — are the three
ways to lose log score, and all three are instances of this one law: `k = 1`,
`k = 1 + ρ`, and `k = z²/(2μ)` respectively. The law is implemented as a tiny
standard-library module (`unify_cost.py`) whose test proves it reproduces each
of the three previously shipped, independently derived cost models exactly.

## 1. The problem

A bot's score in a forecasting tournament is usually attributed to its model's
reasoning. But between the model and the scoreboard sits an extractor: a regex
or parser that must turn `"...so my final probability is about 73%."` into the
number `0.73`. Extractors are brittle and tool-specific. The companion corpus in
this repository ([README](README.md)) measures, across two deployed bots and all
three Metaculus question types, three distinct failure modes:

- a **drop** — the extractor returns nothing, so the question is unforecast;
- a **binary misread** — the extractor returns a confident but wrong answer
  (e.g. reads a base rate mentioned in passing as the forecast);
- a **numeric misread** — the extractor returns a number displaced from the one
  the model intended (e.g. a unit or magnitude slip, `2 million` read as `2.0`).

Each has been priced separately in this repo. The question this note answers:
are these three prices three different phenomena, or three faces of one?

## 2. Setup: the scoring rule

Metaculus FutureEval and its kin score as follows. For each question a bot
answers, its **peer score** is its log score minus the mean log score of the
field on that question. The **Total Score** `S` is the sum of per-question peer
scores; **an unforecast question contributes 0** to that sum. The prize share is
proportional to `max(S, 0)²`, and entries below a floor (currently $50) are not
paid. Write `mu` for the bot's mean per-question peer edge, so a correct read of
a typical question adds `+mu` to `S`, and with `N` questions `S ≈ N·mu` before
errors.

Two features of this rule drive everything below. First, `S` is **additive** over
questions, so one question's error subtracts from `S` independently of the rest.
Second, the prize is **quadratic** in `S`, so a proportional hit to `S` is
roughly doubled in the prize, and a large enough hit zeros the entry outright.

## 3. The unified law

Consider a single extractor error on one question. A correct read would have
contributed `+mu`. Suppose the error instead makes the question's contribution
lose `L_err` nats of log score relative to that correct read. Because `S` is a
plain sum, that one error changes `S` by `-L_err`. Measured against what a single
correct answer is worth, `+mu`, the error costs

> **k = L_err / mu**

*effective dropped answers*. It is as if the bot had thrown away `k` otherwise-
correct answers. If error channel `i` happens at rate `r_i` and each such error
loses `L_i` nats (so `k_i = L_i / mu`), then over `N` questions
`S → N·mu·(1 − Σ r_i k_i)`, and since the prize is proportional to `S²`,

> **expected prize is multiplied by `(max(0, 1 − Σ r_i k_i))²`.**

The bracket clamps at 0: once `Σ r_i k_i ≥ 1` the error load has eaten the entire
edge and the entry scores nothing. For a single channel this gives a **zeroing
rate** `m* = 1/k`.

That is the whole law. The only thing specific to a failure mode is its `L_err`.

## 4. The three instances

Each measured failure mode is one value of `L_err`.

| failure mode | what the extractor does | `L_err` | `k` |
|---|---|---|---|
| **drop** | returns nothing; question lands at the no-forecast value (peer 0) | `mu` (forgo the whole edge) | `1` |
| **binary misread** | posts a confident wrong answer: gives up the edge *and* pays penalty `L` | `mu + L` | `1 + ρ`, with `ρ = L/mu` |
| **numeric misread** | shifts a calibrated Gaussian's centre by `z` standard deviations | `0.5·z²` | `z²/(2μ)` |

- **Drop.** A dropped question scores the no-forecast value, 0, instead of `+mu`.
  Its loss relative to a correct read is the whole edge, `L_err = mu`, so `k = 1`.
  The channel factor `(1 − d)²` is the drop-cost model derived earlier.
- **Binary misread.** The extractor submits the confident opposite answer, which
  earns a *negative* peer score `−L`. Its loss relative to `+mu` is `mu + L`, so
  `k = 1 + ρ` with `ρ = L/mu`. The factor `(1 − m(1+ρ))²` and the zeroing rate
  `1/(1+ρ)` are the binary-misread model.
- **Numeric misread.** A calibrated Gaussian forecast displaced by `z` sigma
  loses exactly `0.5·z²` nats of log score (this is the Gaussian relative-entropy
  of a pure mean shift), so `k = z²/(2μ)`. Unlike the binary case, the penalty is
  *not* a free parameter — it is fixed by geometry and the size of the slip.

## 5. Consequences the single legs could not see together

Putting the three on one axis (`k`) makes the comparisons immediate.

1. **A numeric misread beats a drop only below a break-even displacement.**
   Setting `z²/(2μ) = 1` gives `z* = √(2μ)`. For realistic tournament edges
   (`mu ≈ 0.02–0.1` nats) that is only about `0.2–0.45 σ`. A misread smaller than
   `z*` is cheaper than giving no answer; anything larger is costlier. Most real
   misreads are larger, so **almost any numeric misread is worse than a drop.**
2. **Unit and magnitude slips are catastrophic.** `2 million` read as `2.0`
   displaces the centre by many sigma, so `k` runs into the hundreds: a single
   such misread can erase the edge of hundreds of good forecasts.
3. **Every channel has a zeroing rate `m* = 1/k`.** A drop channel zeros the
   entry only at `d = 1`; a binary misread at `1/(1+ρ)` (≈14% for a worked
   `ρ ≈ 6.1`); a large numeric misread at a rate below 1%.
4. **The design rule for extractors falls out:** minimise `Σ r_i k_i`, and since
   `k` for a misread is `≥ 1` (usually `≫ 1`) while a drop is exactly `1`, a
   *conservative* extractor that drops when unsure strictly dominates an
   aggressive one that guesses, whenever the guess risks `z > z*` or a flipped
   binary answer. Recall is worth chasing only with a guard against reading
   reasoning text as a forecast.

## 6. Reproducibility

`unify_cost.py` implements the law in the standard library only:
`effective_drops`, `drop_k`, `binary_misread_k`, `numeric_misread_k`,
`break_even_displacement`, `prize_factor`, `zeroing_rate`.
`test_unify_cost.py` is self-contained (imports only `unify_cost`) and recomputes
each shipped closed form inline, asserting the unified law reproduces it exactly:
`(1−d)²` for the drop, `(1−m(1+ρ))²` and `1/(1+ρ)` for the binary misread,
`z²/(2μ)` and `z* = √(2μ)` for the numeric misread, and the combined
`(1−d−m(1+ρ))²`. Run `python -m unittest -v`.

## 7. Prior art and limits

Metaculus publishes the peer-score and square-of-sum prize rules, and bot authors
note in passing that an unforecast question "is a zero." What is new here is
connecting an extractor's *format-specific* error rates — the quantities this
repo's corpora actually measure — to the prize through a **single** law
`k = L_err/mu`, and showing that the drop, binary-misread and numeric-misread
costs derived separately are one formula evaluated at three values of `L_err`. A
search of arXiv, Google Scholar and GitHub finds cost models for forecast
*aggregation* and for *scoring-rule* choice, but none that prices a bot's
*answer-extraction* errors against a square-of-sum payout.

Honest limits: `d`, `m`, `ρ` and `z` are scenario inputs, not frequencies
measured from live tournament logs; the model assumes a **non-dominant** entrant
(its own forecasts do not materially move the field mean) and prices the
*extractor*, not the model's reasoning or the downstream distribution
construction. The numeric result assumes a calibrated Gaussian forecast; heavier
tails change the constant in `0.5·z²` but not the `k = L_err/mu` law, which holds
for any `L_err`.

## Cite

See [`CITATION.cff`](CITATION.cff). Code Apache-2.0; corpus data and this text
CC BY 4.0. `forecasting-tools` is a separate Metaculus project, used unmodified,
with full credit to its authors.
