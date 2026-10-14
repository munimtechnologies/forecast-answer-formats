# Cross-tool forecast answer-format robustness

**mv2-forecaster 0.1.7** vs. **Metaculus `forecasting-tools`** — which valid LLM
answer formats each extractor reads, which it silently drops, and when it invents
a forecast that was never there.

Made with AI by MV2 of Munim, Inc. (research field). Code Apache-2.0; data CC BY 4.0.

## Why this exists

A forecasting bot's score depends not only on its reasoning but on whether its
**extractor** can read the model's final answer out of free-form text. When the
extractor returns nothing, that run is dropped from the ensemble (biasing the
aggregate or skipping the question); when it reads a number that was never a
forecast — a base rate, a probability mentioned in passing — it injects a
spurious forecast, which is worse.

Each deployed tool embeds its own private answer regex. There is no public,
standardized corpus that compares which valid formats different *real* extractors
read versus drop, or that measures their false-positive behaviour on reasoning
text. This is the first one. The two extractors compared are both in active use:
mv2-forecaster (an open-source Metaculus bot) and `forecasting-tools`, Metaculus's
own framework whose `PredictionExtractor` the question-template bots call.

## The two extractors (quoted from their live source, read 2026-10-14)

| | mv2-forecaster `parse_binary` | forecasting-tools `extract_last_percentage_value` |
|---|---|---|
| regex | `Probability[\s*_~`]*:[\s*_~`]*(\d+(?:\.\d+)?)\s*(%?)` (`re.I`) | `(\d+(?:\.\d+)?)\s*%` |
| needs the label? | yes — literal `Probability` + colon | no — ignores the label |
| needs a `%`? | no (`%` optional; bare fraction OK) | **yes** |
| picks | last label-match | last `%`-value anywhere |
| no match | returns `None` (drop) | raises (→ drop) |
| out of [0,1] | returns `None` (drop) | raises (→ drop) |

## Binary result (execution-verified)

20 realistic binary answers, each with ground truth: `true_prob`, or `None` when
the text contains **no** legitimate final forecast, so any read is a false
positive. The table below is reproduced exactly by `test_forecast_answer_formats.py`
(run offline from `reference_extractors.py`, transcribed from the sources above)
and by `compare_extractors.py` (which imports the live packages unmodified).

| family | text | true | mv2 | mv2 class | f-tools | ft class |
|---|---|---|---|---|---|---|
| canonical | `Probability: 73%` | 0.73 | 0.73 | correct | 0.73 | correct |
| decimal percent | `Probability: 73.5%` | 0.735 | 0.735 | correct | 0.735 | correct |
| dropped % sign | `Probability: 73` | 0.73 | 0.73 | correct | — | **miss** |
| bare fraction | `Probability: 0.73` | 0.73 | 0.73 | correct | — | **miss** |
| no space | `Probability:73%` | 0.73 | 0.73 | correct | 0.73 | correct |
| whole line bold | `**Probability: 73%**` | 0.73 | 0.73 | correct | 0.73 | correct |
| bold, colon inside | `**Probability:** 73%` | 0.73 | 0.73 | correct | 0.73 | correct |
| number bolded | `Probability: **73%**` | 0.73 | 0.73 | correct | 0.73 | correct |
| italic | `*Probability:* 73%` | 0.73 | 0.73 | correct | 0.73 | correct |
| lowercase | `probability: 73%` | 0.73 | 0.73 | correct | 0.73 | correct |
| numbered line | `1. Probability: 73%` | 0.73 | 0.73 | correct | 0.73 | correct |
| boundary 0% | `Probability: 0%` | 0.0 | 0.0 | correct | 0.0 | correct |
| boundary 100 (no %) | `Probability: 100` | 1.0 | 1.0 | correct | — | **miss** |
| equals separator | `Probability = 73%` | 0.73 | — | **miss** | 0.73 | correct |
| prose 'is' | `My probability is 73%.` | 0.73 | — | **miss** | 0.73 | correct |
| base rate then final | `The base rate is 5%.` ⏎ `Probability: 80%` | 0.80 | 0.80 | correct | 0.80 | correct |
| base rate only (trap) | `Historically about a 5% base rate…` | — | — | correct_reject | 0.05 | **false positive** |
| two prose %s (trap) | `…a 20% chance of rain and a 30% chance of snow.` | — | — | correct_reject | 0.30 | **false positive** |
| out of range | `Probability: 173` | — | — | correct_reject | — | correct_reject |
| no number | `I am fairly confident it happens.` | — | — | correct_reject | — | correct_reject |

**Tally — mv2-forecaster:** 14 correct · 2 miss · **0 false positive** · 4 correct_reject
**Tally — forecasting-tools:** 13 correct · 3 miss · **2 false positive** · 2 correct_reject

## What this shows

Neither extractor dominates; they sit at different points on a precision/recall
frontier, and their silent-loss modes differ **in kind**:

- **mv2-forecaster** is label-gated, so it never reads a number from reasoning
  text (0 false positives) and it reads answers that drop the `%`, use a bare
  fraction, or hit the 100 boundary — but it drops a legitimate forecast written
  with a non-colon separator (`Probability = 73%`) or in prose (`My probability is 73%`).
- **forecasting-tools** reads those non-colon / prose forecasts, but it requires a
  literal `%` (so it drops `Probability: 73`, `Probability: 0.73`, `Probability: 100`),
  and because it takes the last `%`-value *anywhere*, it converts a base rate or a
  prose percentage into a spurious forecast.

The practical upshot for bot authors: a `%`-anywhere extractor maximizes recall on
prose but needs a guard against reasoning-text percentages; a label-gated extractor
needs to accept common non-colon separators to avoid dropping real answers. The
corpus lets anyone place their own extractor on the same frontier.

## Multiple choice (mv2-only)

Confirmed in sealed-container runs (`forecaster-mc-fix-v1`, `forecaster-parser-audit-v1`):
mv2 `parse_multiple_choice` **reads** canonical, numbered (`1.`), bold-colon-inside,
dash-bullet and dropped-`%` lists; it **drops** `=` and parenthetical `(30%)`
formats. The `forecasting-tools` MC API needs a question object, so the cross-tool
MC comparison is future work.

## Honest limits

- The cross-tool comparison is binary-only; MC and numeric-percentile cross-tool
  legs await the library's question-object API.
- The corpus is hand-built to be realistic, not sampled from live bot logs — it is
  a designed probe, not a frequency estimate of how often each format occurs.
- `reference_extractors.py` is a transcription of each tool's published source; it
  is kept faithful to the quoted regexes, and `compare_extractors.py` additionally
  runs the real packages unmodified so results can be checked against live code.

`forecasting-tools` is a separate project by Metaculus, invoked here unmodified for
comparison; all credit for it is theirs.
