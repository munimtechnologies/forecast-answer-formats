# Multiple-choice cross-tool leg

This completes the third question type (after binary and numeric/percentile) in
the first public cross-tool benchmark of which valid LLM answer formats two
*deployed* forecasting-bot extractors read, silently drop, or misread.

Tools compared (unmodified, each used only through its published extractor):

- **mv2-forecaster 0.1.7** `parse_multiple_choice`
  (github.com/munimtechnologies/mv2-forecaster)
- **Metaculus forecasting-tools**
  `prediction_extractor._extract_option_probabilities_through_name_matching`
  (github.com/Metaculus/forecasting-tools) — a separate project, credited to
  Metaculus.

## Result (11 labeled cases, 2 options each, intended 30% / 70%)

| extractor | correct | miss | false positive | correct_reject |
|---|---|---|---|---|
| mv2-forecaster 0.1.7 | 7 | 3 | 0 | 1 |
| Metaculus forecasting-tools | 6 | 4 | 1 | 0 |

As on the binary leg, **neither extractor dominates** — they drop and misread
*different* families.

## Why each result

Both extractors score a line only if it carries an option **name** followed by a
delimiter and a number, so neither is fooled by a stray percentage in prose. The
differences are all in the delimiter grammar.

- **mv2-forecaster** requires a literal `:` but is permissive *around* it: a
  shared `_MC_PAD` class absorbs leading/trailing whitespace, emphasis
  (`* _ ~` and backtick), block-quote `>`, dashes and bullets, plus an explicit
  numbered-list prefix (`1.` / `2)`). The `%` is optional, and all options must
  be found or the whole run is dropped.
- **forecasting-tools** accepts `:` **or** a table-pipe `|`, tolerates leading
  non-word characters, but allows nothing except spaces between the delimiter and
  the number, and its leading `\W*` cannot cross a digit. Exactly one line per
  option must match or the run is dropped.

### Two clean, opposite contrasts

1. **`1. Option A: 30%` (numbered list)** and **`**Option A:** 30%` (bold with
   the colon inside the markers)** → **mv2 reads, forecasting-tools drops.**
   The numbered prefix stops forecasting-tools' leading `\W*` (it cannot cross
   the `1`); the `**` immediately after the colon violates its "only spaces
   between delimiter and number" rule.
2. **`Option A | 30` (markdown table / pipe)** → **forecasting-tools reads, mv2
   drops.** forecasting-tools treats `|` as a valid delimiter; mv2 requires `:`.

### A novel multiple-choice false positive

A reasoning block that prints a reference frequency **table** and then explicitly
declines to forecast —

```
For reference, here are last year's frequencies, which are NOT my forecast:
Option A | 12
Option B | 88
I don't have enough information to forecast this question.
```

— is read by **forecasting-tools** as a 12% / 88% forecast (its pipe support
matches the table rows), a **false positive**. mv2 requires `:` so it correctly
returns nothing. This mirrors the binary leg's base-rate false positive, but the
cause here is *table syntax*, not "last percentage wins."

## Takeaways for bot authors

- If you accept `|` for tables, guard against reading a labeled reference/▸prior
  table as the forecast (e.g. require the forecast lines to be the last option
  block, or ignore blocks under a "not my forecast" heading).
- If you require `:`, also accept the common emphasis-around-colon and
  numbered-list shapes so you don't silently drop a real answer.

## Reproduce

`test_mc_formats.py` recomputes every case offline from faithful transcriptions
of each tool's published source (`mc_extractors.py`) and asserts both the
per-case class and the published tally. Corpus: `xtool_mc_formats.json`
(CC BY 4.0); code Apache-2.0.

## Honest limits

- This is a **designed probe** of realistic formats, not a frequency estimate
  from live tournament logs.
- It models the text **extractors** only, not the downstream distribution
  construction or aggregation.
- The forecasting-tools column is a **source-grounded reproduction**. mv2's MC
  behaviour is additionally confirmed by real sandbox runs
  (`forecaster-mc-fix-v1`, `forecaster-parser-audit-v1`); an independent live
  run of the forecasting-tools package against this corpus
  (`mc-xtool-verify`) is queued to confirm its column too.
- forecasting-tools also tries alias option-name lists (`Option {i}`, bare
  letters, …); irrelevant here because the corpus uses the canonical option
  names verbatim, which reproduces its success path exactly.

*This research and write-up were made with AI, by MV2 of Munim, Inc.*
