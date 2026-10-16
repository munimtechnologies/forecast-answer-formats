# The multiple-choice leg goes three-way: best recall, same missing guard

*Part of forecast-answer-formats, by MV2 of Munim, Inc. Made with AI.
Corpus data CC BY 4.0; code Apache-2.0.*

The third deployed forecasting-bot extractor —
[EskemoMan/metaculus-forecast-bot](https://github.com/EskemoMan/metaculus-forecast-bot),
an open-source entrant in the same Metaculus Fall 2026 FutureEval tournament —
was added to the **binary** leg in v0.9.0 (where it weakly dominated both other
tools) and the **numeric** leg in v0.10.0 (where it read every well-formed
format but had no reasoning-text guard, so no tool dominated). Its
**multiple-choice** leg was the last gap. This release (`eskemo_mc.py`) closes
it, so every corpus in this repo is now scored three-way.

## Result on the 11-case multiple-choice corpus (`xtool_mc_formats.json`)

| extractor | correct | miss | false positive | correct_reject |
|---|---|---|---|---|
| mv2-forecaster 0.1.7 | 7 | 3 | 0 | 1 |
| Metaculus forecasting-tools | 6 | 4 | 1 | 0 |
| **EskemoMan (reimpl., MC)** | **8** | **2** | **0** | **1** |

Per case (✓ read correctly, ✗ silent drop, FP spurious forecast, CR correct
reject):

| case | mv2 | forecasting-tools | EskemoMan |
|---|---|---|---|
| canonical `Option A: 30%` | ✓ | ✓ | ✓ |
| no percent sign | ✓ | ✓ | ✓ |
| decimal fractions | ✓ | ✓ | ✓ |
| dash bullet | ✓ | ✓ | ✓ |
| bold option name | ✓ | ✓ | ✓ |
| bold with colon inside | ✓ | ✗ | ✓ |
| numbered list | ✓ | ✗ | ✓ |
| bare pipe `Option A \| 30` | ✗ | ✓ | ✗ |
| equals `Option A = 30%` | ✗ | ✗ | **✓** |
| parenthetical `Option A (30%)` | ✗ | ✗ | ✗ |
| reference-table trap | CR | FP | CR |

- **EskemoMan weakly dominates mv2-forecaster on this corpus.** It reads
  everything mv2 reads, plus the `=` separator, which **no other tool reads**.
  It accepts `:` or `=`, the same choice its binary path makes.
- **Against forecasting-tools it is a split, not dominance.** EskemoMan reads
  three formats forecasting-tools drops (bold-colon-inside, numbered list,
  `=`), but drops the bare-pipe table row forecasting-tools reads. EskemoMan
  does parse markdown tables, but only rows that **start** with `|`; a row
  written `Option A | 30` with no leading pipe is not a table row to it, and has
  no `:` or `=`, so it is dropped.
- The parenthetical form `Option A (30%)` is still dropped by all three tools.

## The trap rejection is syntax, not a guard

On the one false-positive trap (a model that prints last year's frequency table,
says it is *not* the forecast, and declines), EskemoMan returns nothing, the same
as mv2. But it does so for a **syntactic** reason: the trap's rows have no
leading `|`, so it never sees them as rows. Two probes in `test_eskemo_mc.py`
(not part of the corpus tally) show its multiple-choice path has **no
reasoning-text guard**, as its numeric path has none:

1. **The same declined table written with leading pipes** (`| Option A | 12 |`)
   is read as a 12/88 forecast.
2. **Incomplete final answer falls back to the reasoning.** The parser groups
   matching lines into blocks and tries them from last to first, using the first
   block that names every option. If the final block names only some options,
   it does not drop the run: it silently uses an **earlier** complete block,
   which can be a base rate quoted in the reasoning. In the probe, the reasoning
   quotes last year's 12/88 split and the final answer gives only
   `Option A: 40%`. The parser returns 12/88.

So the three-way picture across all three question types is consistent:
EskemoMan's **binary** path is guarded (label plus a last-four-lines window,
zero false positives); its **numeric** and **multiple-choice** paths are not.
On recall it is the strongest of the three tools on every leg. On guarding
against reasoning text, only its binary path is safe.

### Takeaway for bot authors

- Accept `=` as well as `:` between an option and its probability. It costs
  nothing and no other deployed tool here reads it.
- Treat a table row as a row whether or not it has a leading `|`.
- If the last answer block is incomplete, **drop the run** rather than falling
  back to an earlier complete block. The last block is where the final answer
  is; an earlier one is usually reasoning. A drop costs a run; a fallback can
  post a confident forecast the model never made. (See `misread_cost.md` and
  `PREPRINT.md` for why a misread costs more than a drop.)

## Honesty and method

- **Independent reimplementation, no source copied.** The upstream repo carries
  **no license**. `eskemo_mc.py` is written only from the publicly observable
  behaviour of `forecaster/parsing.py :: parse_multiple_choice` and its helpers
  (read 2026-10-16). No upstream source is copied or redistributed, as with the
  other EskemoMan legs.
- **Hand-traced, then test-gated.** Each of the 11 cases was traced by hand
  through the documented algorithm before the code was written.
  `test_eskemo_mc.py` is self-contained (imports only `eskemo_mc` and the
  standard library). It asserts every per-case class, the full tally (8/2/0/1),
  the `=` result, the leading-pipe versus bare-pipe behaviour, both no-guard
  probes, and that the parser never fills in a default.
- **Same unchanged corpus.** `xtool_mc_formats.json` is not edited; the
  EskemoMan column is computed by the new test, as for the numeric leg.
- **A designed probe, not a frequency estimate.** The 11 cases are chosen to
  separate formats, not sampled from live tournament logs. The two probes show
  that a behaviour exists; they say nothing about how often it fires in
  practice.
- **Text extractor only.** Downstream aggregation is not modelled.
