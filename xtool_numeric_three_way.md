# The numeric leg goes three-way — and this time no tool dominates

*Part of forecast-answer-formats, by MV2 of Munim, Inc. Made with AI.
Corpus data CC BY 4.0; code Apache-2.0.*

In v0.9.0 a third deployed forecasting-bot extractor —
[EskemoMan/metaculus-forecast-bot](https://github.com/EskemoMan/metaculus-forecast-bot),
an open-source entrant in the same Metaculus Fall 2026 FutureEval tournament —
was added to the **binary** leg, where it *weakly dominated* both prior tools: it
kept mv2-forecaster's perfect label gate (zero false positives on every
reasoning-text trap) while also reading the real forecasts that split the other
two. That raised an obvious question: does the same tool dominate the **numeric
(percentile)** leg too?

This release (`eskemo_numeric.py`) answers it. The answer is **no** — and the
reason is interesting.

## Result on the 8-case numeric corpus (`xtool_numeric_formats.json`)

| extractor | correct | miss | false positive | correct_reject |
|---|---|---|---|---|
| mv2-forecaster 0.1.7 | 5 | 2 | 0 | 1 |
| Metaculus forecasting-tools | 5 | 1 | 1 | 0 |
| **EskemoMan (reimpl., numeric)** | **7** | **0** | **1** | **0** |

EskemoMan reads **every well-formed format in the corpus** — more than either
other tool:

- the `Nth percentile:` word order that **mv2 drops** (it requires the literal
  `Percentile N` order);
- the **markdown-bold** percentile block that **forecasting-tools drops** (its
  line filter is anchored at `^\s*`, so a leading `**` kills the line); and
- the **two-point** answer that **mv2 drops** (mv2 requires at least three
  percentiles; EskemoMan instead checks that the *question's declared* levels are
  all present, so a 2-level question with a 2-level answer passes).

So on recall it is strictly the best of the three. But on the one **false-positive
trap** — a model that prints a historical base-rate percentile block and then
*explicitly declines* to give calibrated percentiles — EskemoMan reads the
base-rate block as the forecast, exactly the error forecasting-tools makes. mv2 is
the only tool that rejects it, and only incidentally: it rejects it because the
base-rate lines happen to use the `Nth percentile:` word order mv2 cannot read.

## Why binary dominance did not carry over

EskemoMan's **binary** path has a *reasoning-text guard*: it scans only the last
few non-empty lines and requires a `Probability:` / `Probability =` label, so a
base rate buried in the reasoning cannot become the answer. Its **numeric** path
has **no such guard** — `parse_percentiles` scans *every* line of the whole
response and accepts any line matching a percentile pattern. A disciplined final
answer and a discarded base-rate table are indistinguishable to it.

That is the honest headline: **a per-type asymmetry inside a single deployed
bot.** The same author who built a careful label-and-window guard for binary
answers left the numeric path wide open. It is not that one tool is "better"; it
is that *the guard a tool applies is question-type-specific*, and a bot can be
robust on one answer type and fragile on another. The cross-tool table only makes
this visible because it scores the same three tools on the same probes for every
type.

### Takeaway for bot authors

If you gate your binary extractor against reasoning text (label + last-lines
window), apply the *same discipline to the numeric path*: prefer a final-answer
block (e.g. the last contiguous run of percentile lines, or a block after a
"Final forecast" marker) over "any percentile line anywhere," so a cited
base-rate table cannot be mistaken for the forecast.

## Honesty and method

- **Independent reimplementation, no source copied.** The upstream repo carries
  **no license**. `eskemo_numeric.py` is written only from the publicly
  observable, documented behaviour of `forecaster/parsing.py ::
  parse_percentiles` (and its helpers `normalize`, `unit_scale`, `_apply_scale`).
  No upstream source is copied or redistributed — the same stance this repo takes
  for the other two tools' reference transcriptions and for the binary EskemoMan
  leg.
- **Modelling choice, stated.** `parse_percentiles` takes the question's declared
  percentile levels as its `expected` argument. For each well-formed case we pass
  the levels of its intended distribution; for the trap we pass the standard
  `[10, 50, 90]` the question asked for. This is how a harness calls it and how
  the other two tools are scored on this corpus.
- **A designed probe, not a frequency estimate.** The eight cases are chosen to
  separate formats, not sampled from live tournament logs, so the tallies are
  illustrative of *coverage*, not of how often each format occurs in the wild.
- **Scored offline and test-gated.** `test_eskemo_numeric.py` is self-contained
  (imports only `eskemo_numeric` + the standard library) and asserts every
  per-case value, the full tally (7/0/1/0), the three formats EskemoMan reads
  that another tool drops, and the absence of a numeric reasoning-text guard.

Remaining future work: EskemoMan's **multiple-choice** leg
(`parse_multiple_choice`), which uses a more involved block/renormalisation
algorithm, is not yet scored here.
