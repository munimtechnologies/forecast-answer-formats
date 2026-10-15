# forecast-answer-formats

**The first public cross-tool benchmark of which valid LLM answer formats a
*deployed* forecasting-bot extractor reads, silently drops, or misreads as a
spurious forecast — across all three Metaculus question types: binary,
multiple-choice, and numeric (percentile).**

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

## Results

### Binary (20 cases) — `xtool_answer_formats.json`, `xtool_robustness.md`

| extractor | correct | miss | false positive | correct_reject |
|---|---|---|---|---|
| mv2-forecaster 0.1.7 | 14 | 2 | 0 | 4 |
| Metaculus forecasting-tools | 13 | 3 | 2 | 2 |

mv2-forecaster is label-gated (`Probability:` …): zero false positives, reads
answers that drop the `%`, use a bare fraction, or hit a boundary — but drops a
real forecast written with a non-colon separator (`Probability = 73%`) or in
prose. forecasting-tools takes the last `%`-value anywhere: it reads those prose
/ `=` forecasts, but requires a literal `%`, and because it grabs the last
percentage it can turn a base rate into a spurious forecast.

### Multiple choice (11 cases) — `xtool_mc_formats.json`, `xtool_mc.md`

| extractor | correct | miss | false positive | correct_reject |
|---|---|---|---|---|
| mv2-forecaster 0.1.7 | 7 | 3 | 0 | 1 |
| Metaculus forecasting-tools | 6 | 4 | 1 | 0 |

Two clean, opposite contrasts: mv2 reads numbered lists and bold-colon-inside
lines that forecasting-tools drops; forecasting-tools reads a markdown-table
pipe (`Option A | 30`) that mv2 drops. And a novel MC false positive:
forecasting-tools reads a labeled *reference frequency table* as a forecast,
while mv2 rejects it.

### Numeric / percentile (8 cases) — `xtool_numeric_formats.json`, `xtool_numeric.md`

| extractor | correct | miss | false positive | correct_reject |
|---|---|---|---|---|
| mv2-forecaster 0.1.7 | 5 | 2 | 0 | 1 |
| Metaculus forecasting-tools | 5 | 1 | 1 | 0 |

Opposite contrasts again: on `Nth percentile:` word order, forecasting-tools
reads and mv2 drops; on markdown-bold percentile lines, mv2 reads and
forecasting-tools drops. (forecasting-tools is not asserted on the one
fewer-than-three-percentile case; mv2 requires at least three.)

**Across all three types, neither extractor dominates — they fail on different
families.**

## Files

| file | what it is |
|---|---|
| `xtool_answer_formats.json` | binary + multiple-choice corpus (labeled) |
| `xtool_mc_formats.json` | multiple-choice cross-tool corpus (labeled) |
| `xtool_numeric_formats.json` | numeric/percentile cross-tool corpus (labeled) |
| `reference_extractors.py` | binary reference transcriptions |
| `mc_extractors.py` | multiple-choice reference transcriptions |
| `numeric_extractors.py` | numeric/percentile reference transcriptions |
| `test_forecast_answer_formats.py` | offline recompute of the binary leg |
| `test_mc_formats.py` | offline recompute of the MC leg |
| `test_numeric_formats.py` | offline recompute of the numeric leg |
| `compare_extractors.py` | runs the live packages unmodified |
| `fetch_live.py` | fetches live question objects (optional) |
| `xtool_robustness.md` / `xtool_mc.md` / `xtool_numeric.md` | per-leg write-ups |

## Reproduce

```bash
python -m unittest -v        # recompute all three legs offline
```

Each `test_*.py` recomputes every case from faithful transcriptions of each
tool's published source (`*_extractors.py`) and asserts the per-case class and
the published tally, so a passing suite proves the corpus labels are internally
consistent with the sources. `compare_extractors.py` exercises the live packages
unmodified for independent confirmation.

## Scope and honesty

- A **designed probe** of realistic formats, not a frequency estimate from live
  tournament logs.
- Models the text **extractors** only, not downstream distribution construction
  or aggregation.
- The forecasting-tools columns are **source-grounded reproductions**; mv2's
  behaviour is additionally confirmed by real sandbox runs. An independent live
  run of forecasting-tools against the MC corpus is queued.

Corpus data is **CC BY 4.0**; code is **Apache-2.0**. `forecasting-tools` is a
separate Metaculus project, used unmodified, with full credit to its authors.

*This research and write-up were made with AI, by MV2 of Munim, Inc.*
