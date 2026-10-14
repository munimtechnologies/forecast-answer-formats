# Numeric (percentile) cross-tool answer-format robustness

This extends the binary leg of **forecast-answer-formats** to numeric /
continuous Metaculus questions, where a bot must emit a set of percentiles that
the harness reads into a distribution. As with binary answers, a bot's score
depends not only on its reasoning but on whether its *extractor* can read the
percentile block out of free-form text — and on whether it wrongly reads a
percentile block that was never the final answer.

Prior art: both tools embed private percentile regexes; there is no public,
labeled corpus comparing which valid percentile answer formats deployed
forecasting-bot extractors read versus silently drop, nor measuring their
false-positive behaviour on reasoning text. This is that corpus for the numeric
case. Extractors are transcribed from each tool's published source in
`numeric_extractors.py` and checked offline by `test_numeric_formats.py`; the
live packages are exercised unmodified by `compare_extractors.py`.

## Headline (8 labeled percentile cases)

| extractor | correct | miss | false positive | correct_reject |
|---|---|---|---|---|
| mv2-forecaster 0.1.7 | 5 | 2 | 0 | 1 |
| forecasting-tools | 5 | 1 | 1 | 0 |

(forecasting-tools is not asserted on the `<3`-percentile case; its
distribution-count checks live downstream of the text extractor.)

**Neither dominates — the same precision/recall frontier as the binary leg.**

- **mv2-forecaster** matches only the `Percentile N:` word order but is tolerant
  of markdown emphasis, so it **reads** `**Percentile 50:** 500` and **never
  invents a distribution from reasoning text** (0 false positives). It **drops**
  the common `Nth percentile:` word order and any block with fewer than three
  points.
- **forecasting-tools** accepts both `Percentile N` and `Nth percentile` word
  orders, so it **reads** the ordinal form — but its line filter is anchored at
  the line start, so a leading `**` **drops** a markdown-emphasized block, and
  because it reads any qualifying percentile line it turns a line-anchored
  base-rate block (shown in reasoning, then declined) into a **spurious
  forecast**.

Both tools share robustness to thousands commas, currency symbols, negatives
and zero.

## Takeaway for bot authors

- A line-anchored "any percentile line" extractor maximizes recall on word-order
  variants but needs a guard so a base-rate / reference percentile block in the
  reasoning is not read as the answer.
- A label-gated extractor should also accept the `Nth percentile:` word order
  (and emphasis), which frontier models use often, so it does not silently drop
  a real distribution.

## Honest limits

- A hand-built, designed probe (not a frequency estimate over real transcripts).
- Models the text extractors only, not each library's downstream distribution
  construction (PCHIP fitting, bound pinning, count validation).
- The false-positive case assumes a model that prints a clean, line-anchored
  percentile block and then declines; its frequency in the wild is not measured.

*This research and write-up were made with AI, by MV2 of Munim, Inc.*
