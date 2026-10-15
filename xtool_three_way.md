# A third deployed extractor: the binary benchmark goes three-way

*Part of [forecast-answer-formats](https://github.com/munimtechnologies/forecast-answer-formats),
by MV2 of Munim, Inc. Made with AI.*

The binary leg of this benchmark started as a head-to-head between two deployed
forecasting-bot answer extractors — [mv2-forecaster](https://github.com/munimtechnologies/mv2-forecaster)
and [Metaculus forecasting-tools](https://github.com/Metaculus/forecasting-tools).
This note adds a **third** extractor that is deployed in the *same* tournament
(Metaculus Fall 2026 FutureEval), scored on the *same* 20-case corpus
(`xtool_answer_formats.json`), with no case added or changed. The corpus predates
this extractor, so it is a fair, untuned test.

## The third tool

[`EskemoMan/metaculus-forecast-bot`](https://github.com/EskemoMan/metaculus-forecast-bot)
is an open-source hobbyist entrant whose README states its answers are "parsed
deterministically with regexes, so no extra LLM 'parser' calls are needed." Its
binary parser (`forecaster/parsing.py :: parse_binary_probability`) is therefore
a pure, reproducible function of the text — ideal for this benchmark.

`eskemo_extractor.py` here is an **independent reimplementation** of that
parser's publicly documented behaviour. The upstream repository carries **no
license file**, so none of its source is copied or redistributed; only the
observable algorithm is reproduced, exactly as this repo already does with
"reference transcriptions" of the other two tools. `test_eskemo_extractor.py`
asserts the per-case value and class offline.

Its binary rule, in one sentence: scan only the **last four non-empty lines** in
reverse for a line containing the word *probability* with a `:` **or** `=`
separator; accept a bare number or fraction (a `%` is optional); and **drop**
(never guess) on no match, an out-of-range value, or a stated range.

## Three-way binary result (20 cases)

| extractor | correct | miss | false positive | correct_reject |
|---|---|---|---|---|
| mv2-forecaster 0.1.7 | 14 | 2 | 0 | 4 |
| Metaculus forecasting-tools | 13 | 3 | 2 | 2 |
| **EskemoMan (reimpl.)** | **15** | **1** | **0** | **4** |

## The finding

With only two tools the headline was *neither extractor dominates* — each read
formats the other dropped. **The third tool breaks that symmetry on this corpus:
EskemoMan's parser weakly dominates both.** It matches mv2-forecaster's perfect
label-gating (0 false positives; all four reasoning-text traps correctly
rejected) while *also* reading the three formats that split the first two:

- `Probability = 73%` — the `=` separator mv2-forecaster drops (it reads only `=`
  **and** `:`), and
- `Probability: 73` and `Probability: 100` — bare numbers with no `%` that
  forecasting-tools drops (it requires a literal `%`).

Its **only** miss is a forecast written in pure prose with no separator at all —
`My probability is 73%.` — which forecasting-tools alone reads (by grabbing the
last `%` anywhere), at the cost of its two false positives.

### Design principle this isolates

Three independent design choices, each individually sensible, compose into the
best binary extractor observed here:

1. **Gate on the label word** (`probability`) → zero false positives on
   reasoning text (base rates, prose percentages, reference figures).
2. **Accept both `:` and `=` separators, and make the `%` optional** → recover
   the common real forecasts the stricter two tools drop.
3. **Scope to the last few lines** → the label gate can be loosened without
   re-admitting an early-paragraph base rate as a false positive.

The residual blind spot — a separator-less prose forecast — is exactly the case a
`%`-anywhere reader catches. So the honest takeaway is a *hybrid*: a label-and-
separator gate scoped to the final lines, with a `%`-anywhere pass as a
last-resort fallback, would read every legitimate format in this corpus with no
false positive. No single deployed tool does both today.

## Honest limits

- **Binary only.** EskemoMan also has `parse_percentiles` and
  `parse_multiple_choice`; scoring those against the numeric and MC corpora is
  future work, left out here rather than guessed at.
- **A designed 20-case probe, not a live-frequency estimate.** "Weakly
  dominates" is a statement about *this* corpus. The prose-without-separator
  family has a single case; a corpus weighted toward prose would narrow or
  reverse the gap, since that family is EskemoMan's and mv2's shared blind spot
  and forecasting-tools' strength.
- **Reference reimplementation**, not the upstream package executed in-process.
  The documented behaviour is reproduced faithfully (normalisation, the
  separator set, the last-four-lines scan, unit handling, range/out-of-range
  rejection, drop-not-guess), but subtle upstream edge cases outside these 20
  formats are not claimed.
