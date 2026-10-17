# forecast-answer-formats

**The first public cross-tool benchmark of which valid LLM answer formats a
*deployed* forecasting-bot extractor reads, silently drops, or misreads as a
spurious forecast — across all three Metaculus question types: binary,
multiple-choice, and numeric (percentile) — plus tested models of what a drop and
a misread each cost in the tournament prize.**

A forecasting bot's score depends not only on how well its model reasons, but on
whether the bot's *extractor* can read the model's final answer out of free-form
text. If the extractor returns nothing, that run is dropped from the ensemble; if
it reads a number that was never a forecast — a base rate, a figure mentioned in
passing, a reference table — it injects a spurious one, which is worse. Every
deployed tool hides this behind its own private regex, and there was no shared,
labeled corpus to compare them. This repo is that corpus plus a reproduction
harness.

Tools compared (each used unmodified, through its published extractor only):

- **mv2-forecaster** (github.com/munimtechnologies/mv2-forecaster), by MV2 of
  Munim, Inc.
- **Metaculus forecasting-tools**
  (github.com/Metaculus/forecasting-tools) — a separate project by Metaculus,
  credited as such.
- **EskemoMan/metaculus-forecast-bot** (all three legs) — a separate
  open-source hobbyist entrant in the same Fall 2026 FutureEval tournament, scored
  here via an independent reimplementation of its documented regex parsers (that
  repo carries no license; no source is copied). See `xtool_three_way.md`,
  `xtool_numeric_three_way.md` and `xtool_mc_three_way.md`.
- **Bowen1314/metaculus-bot** (binary leg) — a fourth entrant in the same
  tournament (MIT; notice in `THIRD_PARTY_NOTICES.md`). Its deterministic binary
  parser is scored here; when that parser returns nothing, the deployed bot hands
  the text to an LLM parser, which is not run here. See `xtool_four_way.md`.
- **Torrin44/forecast-bot** (binary leg) — a fifth entrant in the same
  tournament (MIT; notice in `THIRD_PARTY_NOTICES.md`). Its deterministic binary
  parser is scored here; a `ParseError` defers to a 6,000-char LLM repair parser,
  not run here. On the corpus it is identical to forecasting-tools; probes show
  three structural differences. See `xtool_five_way.md`.

## Results

### Binary (20 cases) — `xtool_answer_formats.json`, `xtool_robustness.md`, `xtool_three_way.md`, `xtool_four_way.md`, `xtool_five_way.md`

| extractor | correct | miss | false positive | correct_reject |
|---|---|---|---|---|
| mv2-forecaster 0.1.7 | 14 | 2 | 0 | 4 |
| Metaculus forecasting-tools | 13 | 3 | 2 | 2 |
| EskemoMan (reimpl., binary) | 15 | 1 | 0 | 4 |
| Bowen1314 (regex stage) | 12 | 4 | 0 | 4 |
| Torrin44 (regex stage) | 13 | 3 | 2 | 2 |

mv2-forecaster is label-gated (`Probability:` …): zero false positives, reads
answers that drop the `%`, use a bare fraction, or hit a boundary — but drops a
real forecast written with a non-colon separator (`Probability = 73%`) or in
prose. forecasting-tools takes the last `%`-value anywhere: it reads those prose
/ `=` forecasts, but requires a literal `%`, and because it grabs the last
percentage it can turn a base rate into a spurious forecast. The third tool,
**EskemoMan**, weakly dominates both on this corpus (15/1/0/4): it keeps the
label gate (0 false positives) but accepts *both* `:` and `=` and an optional
`%`, and scopes the scan to the last few lines — so its only miss is a
separator-less prose forecast, exactly the case forecasting-tools catches. Full
analysis and the design principle it isolates are in `xtool_three_way.md`.

The fourth tool, **Bowen1314**, is forecasting-tools' `%`-required rule behind a
label gate. It matches forecasting-tools on every case except three: it drops the
prose forecast and rejects both reasoning-text traps, giving up one read to avoid
two false positives. EskemoMan weakly dominates it; against mv2 it is a split
(`=` vs the no-`%` forms). It is also a two-stage design: its 4 misses
and 4 rejects go to an LLM parser in the deployed bot, so the misses cost an
extra call rather than a dropped run. Whether that LLM parser reads the traps
safely is not measured. Verified in a sealed sandbox run that first reproduced
the published mv2 and forecasting-tools tallies (`xtool_four_way.json`). See
`xtool_four_way.md`.

The fifth tool, **Torrin44**, is the sharpest result of the set: its
deterministic stage is **identical to forecasting-tools on all 20 corpus cases**
(same 13/3/0/2/2, case by case), yet it is a different parser. Twelve structural
probes, machine-verified against both upstream sources, show where: Torrin's
fallback scans only the **last 300 characters** (so a far-away base rate FT reads
is dropped, but a real trailing answer can be truncated — `Final answer 45%` is
read as `5%`), and its number grammar matches a leading dot and comma groups
(`.5%` → 0.005, not FT's 0.05; `1,000%` → rejected, not FT's 0.0). Two
independently written parsers converge to the same behaviour on well-formed
answers, false positives included, and diverge only on malformed ones. Verified
in the same sealed run (Gate A + Gate B, 0 parity mismatches over 32 texts). See
`xtool_five_way.md`.

### Multiple choice (11 cases) — `xtool_mc_formats.json`, `xtool_mc.md`, `xtool_mc_three_way.md`

| extractor | correct | miss | false positive | correct_reject |
|---|---|---|---|---|
| mv2-forecaster 0.1.7 | 7 | 3 | 0 | 1 |
| Metaculus forecasting-tools | 6 | 4 | 1 | 0 |
| EskemoMan (reimpl., MC) | 8 | 2 | 0 | 1 |

Two clean, opposite contrasts between the first two tools: mv2 reads numbered
lists and bold-colon-inside lines that forecasting-tools drops; forecasting-tools
reads a markdown-table pipe (`Option A | 30`) that mv2 drops. And a novel MC
false positive: forecasting-tools reads a labeled *reference frequency table* as
a forecast, while mv2 rejects it. The third tool, **EskemoMan**, weakly
dominates mv2 here: it reads everything mv2 reads plus `Option A = 30%`, which
no other tool reads. It drops the bare-pipe row (it treats a line as a table row
only if it *starts* with `|`). It rejects the corpus trap only for that
syntactic reason: probes show it reads the same declined table written with
leading pipes, and that when the final answer block is incomplete it silently
falls back to an *earlier* complete block from the reasoning. See
`xtool_mc_three_way.md`.

### Numeric / percentile (8 cases) — `xtool_numeric_formats.json`, `xtool_numeric.md`, `xtool_numeric_three_way.md`

| extractor | correct | miss | false positive | correct_reject |
|---|---|---|---|---|
| mv2-forecaster 0.1.7 | 5 | 2 | 0 | 1 |
| Metaculus forecasting-tools | 5 | 1 | 1 | 0 |
| EskemoMan (reimpl., numeric) | 7 | 0 | 1 | 0 |

Opposite contrasts again between the first two: on `Nth percentile:` word order,
forecasting-tools reads and mv2 drops; on markdown-bold percentile lines, mv2
reads and forecasting-tools drops. The third tool, **EskemoMan**, reads *every*
well-formed format in the corpus — the `Nth percentile:` word order, the
markdown-bold block, *and* the two-point answer mv2 drops — but, unlike its own
binary path, its numeric path has **no reasoning-text guard**, so it reads a
declined base-rate block as a forecast (the same false positive forecasting-tools
makes). So on numeric **no tool dominates**: the one tool with a binary guard
left its numeric path open. See `xtool_numeric_three_way.md`.

**Across all three legs, EskemoMan has the best recall, but only its binary
path guards against reading reasoning text as the answer. On binary it weakly
dominates all three other tools; on multiple-choice it weakly dominates mv2 and
splits with forecasting-tools; on numeric it commits the base-rate false
positive, so no tool dominates.**

## What a drop or a misread costs in the tournament

The corpora above show *which* formats each tool drops or misreads. A family of
small, test-gated, pure-standard-library models prices *what that costs* under the
Metaculus tournament rule — Total Score `S` = sum of per-question peer scores
(an unforecast question is 0); prize share ∝ `max(S, 0)**2`; prizes under $50 not
paid. Each is derived and checked by an offline test plus a Monte Carlo over a
realistic non-dominant pool.

| model | file | result |
|---|---|---|
| **Drop** | `drop_cost.py`, `drop_cost.md` | A silent-drop rate `d` scales Total Score by `(1-d)`, so the prize by `(1-d)**2` — about twice the raw rate. |
| **Misread (binary)** | `misread_cost.py`, `misread_cost.md` | A misread posts a *confident wrong* forecast (negative peer `-L`); with `rho = L/mu` it costs `(1+rho)` drops, prize factor `(max(0, 1 - m*(1+rho)))**2`, and zeros the entry once `m > 1/(1+rho)`. |
| **Combined** | `combined_cost.py`, `combined_cost.md` | Drops and misreads together act as one effective drop rate `d + m*(1+rho)`; `from_corpus_tally()` maps a tool's measured tally straight to a prize factor. |
| **Misread (numeric)** | `numeric_misread_cost.py`, `numeric_misread_cost.md` | A numeric misread's penalty is *not* free — for a Gaussian forecast it is `0.5*z**2` nats for a displacement of `z` standard deviations, so it costs `z**2/(2*mu)` drops. A misread beats a drop only below the break-even displacement `z* = sqrt(2*mu)` ≈ 0.2–0.45 σ for realistic edges; a unit/magnitude error ("2 million" read as "2.0") is catastrophic. |

The drop and both misread legs share one law: an extractor error that loses
`L_err` nats of log score relative to a correct read costs `k = L_err / mu`
*effective dropped answers* — `k = 1` for a drop, `k = 1 + rho` for a binary
misread, `k = z**2/(2*mu)` for a numeric one — and a set of error channels at
rates `r_i` multiplies the expected prize by `(max(0, 1 - sum_i r_i*k_i))**2`.
This unification is derived in **[`PREPRINT.md`](PREPRINT.md)** and implemented in
`unify_cost.py`, whose test proves it reproduces each of the three shipped cost
models exactly.

## Files

| file | what it is |
|---|---|
| `xtool_answer_formats.json` | binary + multiple-choice corpus (labeled) |
| `xtool_mc_formats.json` | multiple-choice cross-tool corpus (labeled) |
| `xtool_numeric_formats.json` | numeric/percentile cross-tool corpus (labeled) |
| `xtool_four_way.json` | binary leg, per-case values and classes for four tools (sandbox-verified) |
| `xtool_five_way.json` | binary leg, per-case values and classes for all five tools + 12 structural probes (sandbox-verified) |
| `reference_extractors.py` | binary reference transcriptions |
| `mc_extractors.py` | multiple-choice reference transcriptions |
| `numeric_extractors.py` | numeric/percentile reference transcriptions |
| `eskemo_extractor.py` | binary reference reimpl. of a third deployed extractor (with `test_eskemo_extractor.py`) |
| `eskemo_numeric.py` | numeric reference reimpl. of the same third extractor (with `test_eskemo_numeric.py`) |
| `eskemo_mc.py` | multiple-choice reference reimpl. of the same third extractor (with `test_eskemo_mc.py`) |
| `bowen_binary.py` | binary parser of a fourth deployed extractor, Bowen1314/metaculus-bot (with `test_bowen_binary.py`) |
| `torrin_binary.py` | binary parser of a fifth deployed extractor, Torrin44/forecast-bot (with `test_torrin_binary.py`) |
| `test_forecast_answer_formats.py` | offline recompute of the binary leg |
| `test_mc_formats.py` | offline recompute of the MC leg |
| `test_numeric_formats.py` | offline recompute of the numeric leg |
| `compare_extractors.py` | runs the live packages unmodified |
| `fetch_live.py` | fetches live question objects (optional) |
| `drop_cost.py` / `misread_cost.py` / `combined_cost.py` / `numeric_misread_cost.py` | tournament cost models (with `test_*` and `*.md`) |
| `unify_cost.py` | the single law `k = L_err/mu` the four cost models share (with `test_unify_cost.py`) |
| `PREPRINT.md` | short write-up deriving the unified cost law |
| `xtool_robustness.md` / `xtool_mc.md` / `xtool_numeric.md` / `xtool_three_way.md` / `xtool_numeric_three_way.md` / `xtool_mc_three_way.md` / `xtool_four_way.md` / `xtool_five_way.md` | per-leg write-ups |
| `THIRD_PARTY_NOTICES.md` | licences of the other projects whose logic is used here |

## Reproduce

```bash
python -m unittest -v        # recompute every leg and cost model offline
```

Each `test_*.py` recomputes every case from faithful transcriptions of each
tool's published source (`*_extractors.py`) and asserts the per-case class and
the published tally, so a passing suite proves the corpus labels are internally
consistent with the sources. The cost-model tests check each analytic law against
a Monte Carlo. `compare_extractors.py` exercises the live packages unmodified for
independent confirmation.

## Scope and honesty

- A **designed probe** of realistic formats, not a frequency estimate from live
  tournament logs.
- Models the text **extractors** only, not downstream distribution construction
  or aggregation.
- The forecasting-tools columns are **source-grounded reproductions**; mv2's
  behaviour is additionally confirmed by real sandbox runs. The EskemoMan columns
  are independent reimplementations of a no-license public repo's documented
  algorithm (no source copied), for all three legs. An independent live run of
  forecasting-tools against the MC corpus is queued.
- The Bowen1314 and Torrin44 columns cover their **deterministic binary stage
  only**. Each ports an upstream `bot/parsing.py` function and is machine-verified
  byte-for-behaviour equal to it (Gate B, 0 mismatches). Their LLM fallbacks were
  not run, so the deployed bots' end-to-end handling of the cases their regex
  passes on is unknown.
- The cost models price scenarios (`d`, `m`, `rho`, `z` are inputs, not measured
  frequencies) and assume a non-dominant entrant; each states its limits.

Corpus data is **CC BY 4.0**; code is **Apache-2.0**. `forecasting-tools` is a
separate Metaculus project, used unmodified, with full credit to its authors.
`bowen_binary.py` follows Bowen1314/metaculus-bot (MIT, Copyright (c) 2026
Bowen Rui); `torrin_binary.py` follows Torrin44/forecast-bot (MIT, Copyright (c)
2026 the forecast-bot authors); see `THIRD_PARTY_NOTICES.md`.

*This research and write-up were made with AI, by MV2 of Munim, Inc.*
