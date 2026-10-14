# forecast-answer-formats

**The first public cross-tool benchmark of which valid LLM answer formats
forecasting-bot extractors silently drop — and when they invent a forecast that
was never there.**

A forecasting bot's score depends not just on its reasoning but on whether its
*extractor* can read the model's final answer out of free-form text. If the
extractor returns nothing, that run is dropped from the ensemble; if it reads a
number that was never a forecast (a base rate, a figure mentioned in passing), it
injects a spurious one. Every deployed tool hides this behind its own private
regex, and — until now — there was no shared, labeled corpus to compare them.

This repo ships:

- **`xtool_answer_formats.json`** — a labeled corpus of realistic LLM
  structured-answer strings (binary, multiple-choice, numeric percentiles), each
  with ground truth, plus both extractors' per-case results. *(CC BY 4.0)*
- **`xtool_robustness.md`** — the write-up: the quoted source regexes, the full
  binary results table, and what the precision/recall frontier means for bot
  authors.
- **`reference_extractors.py`** — self-contained transcriptions of each tool's
  published binary extractor, so the headline result is reproducible offline.
- **`test_forecast_answer_formats.py`** — recomputes every binary case from the
  reference extractors and asserts the dataset's per-case classes and headline
  tallies. `python -m unittest -v` — no network, no third-party installs.
- **`compare_extractors.py`** + **`fetch_live.py`** — run the corpus through the
  *live* packages unmodified (fetches mv2-forecaster `main`, pip-installs
  `forecasting-tools`) and regenerate the JSON, so the numbers can be checked
  against the real code.

## Headline result (binary, 20 cases)

| extractor | correct | miss | false positive | correct_reject |
|---|---|---|---|---|
| mv2-forecaster 0.1.7 | 14 | 2 | **0** | 4 |
| Metaculus forecasting-tools | 13 | 3 | **2** | 2 |

Neither dominates. mv2-forecaster is label-gated: zero false positives, reads
dropped-`%`/bare-fraction answers, but drops non-colon (`Probability = 73%`) and
prose forecasts. forecasting-tools reads prose and `=` forecasts but requires a
literal `%` (dropping `Probability: 73`, `0.73`, `100`) and, taking the last `%`
anywhere, turns a base rate or a prose percentage into a spurious forecast. Full
table and discussion in [`xtool_robustness.md`](xtool_robustness.md).

## Reproduce

```bash
# offline, from the transcribed reference extractors (what the CI test runs):
python -m unittest -v

# against the live packages:
pip install forecasting-tools
python fetch_live.py          # pulls mv2-forecaster main
python compare_extractors.py --out-dir .
```

## Scope and honesty

The cross-tool comparison is binary-only (the tools' binary APIs are directly
comparable); MC/numeric cross-tool legs await the library's question-object API.
The corpus is a designed probe of realistic formats, not a frequency estimate from
live logs. `forecasting-tools` is a separate project by Metaculus, invoked here
unmodified for comparison — all credit for it is theirs.

This work was made with AI, by **MV2 of Munim, Inc.** Code is Apache-2.0; the
corpus data is CC BY 4.0.
