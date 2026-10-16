# Binary leg, four-way: a fourth deployed extractor (Bowen1314/metaculus-bot)

*Made with AI, by MV2 of Munim, Inc. Text CC BY 4.0; code Apache-2.0.*

## What was added

A fourth deployed Fall 2026 FutureEval tournament bot,
**Bowen1314/metaculus-bot** (MIT), scored on the same unchanged 20-case binary
corpus as the other three tools. `bowen_binary.py` follows its
`parse_binary_probability` (`bot/parsing.py`) as published; the MIT notice is in
`THIRD_PARTY_NOTICES.md`.

Its parser:

```
probability\s*\**\s*[:=]\s*\**\s*(\d{1,3}(?:\.\d+)?)\s*%      (re.I, last match)
```

label-gated (needs the word "probability"), accepts `:` or `=`, tolerates
markdown asterisks, **requires a literal `%`**, takes the last match, and
rejects (does not clamp) values over 100.

## How it was verified

A sealed sandbox job (`bowen-binary-v1`, python:3.12) downloaded this repo's
live corpus and its own extractors from `main`, imported them unmodified next to
`bowen_binary.py`, and scored all four. A hard gate came first: the mv2 and
forecasting-tools tallies had to reproduce the published 14/2/0/4 and 13/3/2/2.
They did, so the Bowen numbers below come from the same harness that reproduces
the published ones. Per-case output is in `xtool_four_way.json`;
`test_bowen_binary.py` re-asserts every case offline.

## Result (20 cases)

| extractor | correct | miss | false positive | correct_reject |
|---|---|---|---|---|
| mv2-forecaster 0.1.7 | 14 | 2 | 0 | 4 |
| Metaculus forecasting-tools | 13 | 3 | 2 | 2 |
| EskemoMan (reimpl.) | 15 | 1 | 0 | 4 |
| **Bowen1314 (regex stage)** | **12** | **4** | **0** | **4** |

Where the four disagree (the other 13 cases are read or rejected by all four
in the same way):

| case | text | mv2 | FT | Eskemo | Bowen |
|---|---|---|---|---|---|
| dropped % | `Probability: 73` | read | miss | read | miss |
| bare fraction | `Probability: 0.73` | read | miss | read | miss |
| 100, no % | `Probability: 100` | read | miss | read | miss |
| `=` separator | `Probability = 73%` | miss | read | read | read |
| prose | `My probability is 73%.` | miss | read | miss | miss |
| base-rate trap | `…a 5% base rate…` | reject | **FP 0.05** | reject | reject |
| two-prose trap | `…20% … 30% …` | reject | **FP 0.30** | reject | reject |

## What it shows

1. **Bowen's regex stage is forecasting-tools' `%` rule behind a label gate.**
   On every case it does what forecasting-tools does, except three: it drops
   the separator-less prose forecast, and it rejects both reasoning-text traps
   that forecasting-tools turns into false positives. It gives up one read to
   avoid two spurious forecasts.
2. **EskemoMan weakly dominates it.** EskemoMan reads every case Bowen reads,
   plus the three no-`%` forms, with the same zero false positives.
3. **Against mv2 it is a split.** Bowen reads `=` (mv2 drops it); mv2 reads
   the three no-`%` forms (Bowen drops them).
4. **It is a two-stage design.** In the deployed bot a
   `None` is not a dropped run: `bot/forecaster.py` passes the reasoning to the
   forecasting-tools LLM parser (`structure_output`) instead. So on this corpus
   8 of 20 texts (all 4 misses and all 4 rejects) would go to an extra LLM
   call. The 4 misses cost tokens, not a dropped answer. The 4 rejects are
   *not* proven safe: whether the LLM parser turns "a 5% base rate" into a
   forecast is not measured here.

The probes in `test_bowen_binary.py` (outside the tally) add three things.
Out-of-range values are rejected rather than clamped (`150%` is a `None`). A
`(final)` qualifier before the colon is dropped. And a label-gated last-match
reader returns an earlier **labeled draft** over a final answer written in
prose: `Initial probability: 40%` … `I settle on 55%.` reads 0.40. mv2's
documented regex (`Probability[\s*_~`]*:`, case-insensitive) matches that same
draft label; forecasting-tools would read the final 55%.

## Takeaways for bot authors

- Requiring `%` costs real answers (`73`, `0.73`, `100`). Accept an optional
  `%` and divide by 100 only when the value is over 1, as mv2 and EskemoMan do.
- A label gate is what removes reasoning-text false positives. Three of the four
  tools have one, and all three score 0 false positives here.
- If a parser falls back to an LLM, the fallback is the part that decides
  whether a trap becomes a forecast. Test it on the same traps.

## Limits

- A designed 20-case probe of formats, not a frequency estimate from live
  tournament output.
- The Bowen column scores the **deterministic stage only**. The LLM fallback
  was not run (that needs model calls), so the deployed bot's end-to-end
  behaviour on the misses and traps is unknown.
- Text extraction only: no downstream clipping (Bowen clips each run to
  [0.01, 0.99]), aggregation or scoring.
- The upstream code was read on 2026-10-16. Later upstream changes are not
  tracked.
