# Binary leg, five-way: a fifth deployed extractor (Torrin44/forecast-bot)

*Made with AI, by MV2 of Munim, Inc. Text CC BY 4.0; code Apache-2.0.*

## What was added

A fifth deployed Fall 2026 FutureEval tournament bot,
**Torrin44/forecast-bot** (MIT), scored on the same unchanged 20-case binary
corpus as the other four tools. `torrin_binary.py` follows its `parse_binary`
(`bot/parsing.py`) as published; the MIT notice is in `THIRD_PARTY_NOTICES.md`.

Its deterministic parser:

```
probability\s*[:=]\s*\**\s*(_NUM)\s*%      (re.I, last match)   # primary, label-gated
(_NUM)\s*%   on text[-300:]                (last match)         # fallback, any "%"
_NUM = [-+]?\d[\d,]*(?:\.\d+)?|[-+]?\.\d+
```

It prefers a `probability:`/`probability=` label (accepts `:` or `=`, tolerates
markdown asterisks, requires a literal `%`, last match wins). If **no** labeled
match exists, it falls back to the last bare `N%` in the **final 300 characters**
of the text. It strips commas, rejects (does not clamp) values outside 0–100,
and otherwise raises `ParseError` — which the deployed bot sends to a 6,000-char
LLM repair parser, so a `None` here is a token cost, not a dropped run.

## How it was verified

A sealed sandbox job (`upstream-parity-v2`, python:3.12) downloaded this repo's
live corpus and extractors from `main`, plus the upstream `bot/parsing.py` of
both ported bots, and scored all five. Two hard gates came first:

- **Gate A** — the mv2 and forecasting-tools tallies had to reproduce the
  published 14/2/0/0/4 and 13/3/0/2/2. **PASS.**
- **Gate B** — on all 20 corpus texts **and** 12 probe texts, the `bowen` and
  `torrin` ports had to return exactly what the upstream functions return
  (`ParseError` mapped to `None`). **PASS: 0 mismatches over 32 texts each.**

So the Torrin numbers below come from the same harness that reproduces the
published ones, and the port is byte-for-behaviour equal to the upstream
function. Per-case output is in `xtool_five_way.json`; `test_torrin_binary.py`
re-asserts every case offline.

## Result (20 cases)

| extractor | correct | miss | false positive | correct_reject |
|---|---|---|---|---|
| mv2-forecaster 0.1.7 | 14 | 2 | 0 | 4 |
| Metaculus forecasting-tools | 13 | 3 | 2 | 2 |
| EskemoMan (reimpl.) | 15 | 1 | 0 | 4 |
| Bowen1314 (regex stage) | 12 | 4 | 0 | 4 |
| **Torrin44 (regex stage)** | **13** | **3** | **2** | **2** |

## The headline finding: identical on the corpus, different parsers

**Torrin's deterministic binary stage is identical to forecasting-tools on all
20 corpus cases** — not just the same tally (13/3/0/2/2) but the same read or
drop on every single case, including reading the `=` separator and the prose
`My probability is 73%` that mv2 drops, and committing the same two reasoning-text
false positives (`a 5% base rate` → 0.05; `20% … 30%` → 0.30). On the 20-case
corpus the two are indistinguishable.

They are **not** the same parser, though. Twelve probe texts outside the tally
(all machine-verified against both upstream sources) expose three structural
differences that the corpus happens not to trigger:

| probe | forecasting-tools | Torrin | why they differ |
|---|---|---|---|
| base rate `5%` then ~450 chars of filler | 0.05 (FP) | **None** | Torrin's fallback only scans the **last 300 chars**; FT scans the whole text |
| `Final answer 45%` then filler to len 314 | 0.45 | **0.05** | Torrin's 300-char window starts **mid-number**, slicing `45%` to `5%` |
| `Probability: .5%` | 0.05 | **0.005** | Torrin's `_NUM` matches a **leading dot**; FT's does not, so FT reads the bare `5` |
| `Probability: 1,000%` | 0.0 | **None** | Torrin's `_NUM` matches the **comma group** `1,000` → out of range → reject; FT reads `000` → 0.0 |
| `Probability: +12%` | 0.12 | 0.12 | both read a signed number |

So forecasting-tools and Torrin agree on every *well-formed* answer but diverge
on *malformed* ones: Torrin's 300-char window is a crude guard that happens to
block a far-away base rate FT reads, but it can also truncate a real trailing
answer; and Torrin's richer number grammar rejects a comma-grouped out-of-range
value FT silently turns into 0.0. **Neither is uniformly safer** — Torrin's
window removes one of FT's false positives only when the stray percentage sits
more than 300 characters from the end.

## What it shows

1. **Two independently written tournament parsers converge to the same
   behaviour on realistic answers.** Torrin and forecasting-tools are the only
   two of the five tools that read the `=` separator *and* the separator-less
   prose forecast, and they are the only two that commit the base-rate and
   two-prose false positives — because both are "last `%`-value, label-preferring,
   `%`-required" designs. The "`%`-anywhere, grab the last one" idiom reproduces
   exactly, false positives included, when authors reinvent it.
2. **A trailing-window fallback is a weak and double-edged guard.** Torrin's
   300-char window is the only thing that distinguishes its false-positive profile
   from forecasting-tools, and it is as likely to truncate a genuine trailing
   answer (`Final answer 45%` → `5%`) as to hide a stray base rate. A label gate
   (mv2, Eskemo, Bowen) removes the reasoning-text false positives outright.
3. **It is a two-stage design, like Bowen and forecasting-tools.** In the
   deployed bot a `ParseError` is not a dropped run: `bot/forecaster.py` sends the
   last 6,000 characters to a parser model. So Torrin's 3 misses and 2 rejects on
   this corpus cost an extra LLM call, not a dropped answer. Whether that repair
   parser turns the two traps into forecasts is not measured here.

## Takeaways for bot authors

- If you reuse the "last `%`-value" idiom, you inherit its reasoning-text false
  positives. A label gate is what removes them; three of the five tools have one
  and all three score 0 false positives here.
- A trailing-character window is not a substitute for a label gate: it can
  silently truncate a real answer or slice a number in half. If you fall back to a
  window, anchor it to a line or sentence boundary, not a raw character count.
- Match a comma-grouped, out-of-range value (`1,000%`) explicitly and reject it,
  rather than letting a narrow `\d+` read a fragment of it.

## Limits

- A designed 20-case probe of formats plus 12 structural probes, not a frequency
  estimate from live tournament output.
- The Torrin column scores the **deterministic stage only**. The LLM repair
  parser was not run (that needs model calls), so the deployed bot's end-to-end
  behaviour on the misses and traps is unknown.
- Text extraction only: no downstream clipping, aggregation or scoring.
- The upstream code was read on 2026-10-16. Later upstream changes are not
  tracked.
