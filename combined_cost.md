# Drops and misreads together: one prize factor, tied to the corpus tallies

*Made with AI, by MV2 of Munim, Inc. Part of
[forecast-answer-formats](https://github.com/munimtechnologies/forecast-answer-formats).
Apache-2.0 (code) / CC BY 4.0 (text).*

[`drop_cost.py`](drop_cost.py) priced a silent **drop** (extractor returns nothing
→ peer `0`) as a prize factor `(1-d)**2`. [`misread_cost.py`](misread_cost.py)
priced a silent **misread** (extractor returns a number that was never the
forecast → a confident wrong forecast → a **negative** peer `-L`, with
`rho = L/mu`) as `(max(0, 1 - m*(1+rho)))**2`. A real extractor does **both**, and
this repo's cross-tool corpora report, per tool, how many answerable cases it
**drops** (a *miss*) and how many it **misreads** (a *false positive*). This note
combines the two into a single prize factor and connects it straight to those
tallies.

## The law

On each of `N` questions the bot either reads correctly (earns edge `mu > 0`),
drops (peer `0`), or misreads (peer `-L = -rho*mu`). With drop rate `d` and misread
rate `m` (`d + m ≤ 1`):

```
S = N*mu * [ (1 - d - m) - m*rho ] = N*mu * [ 1 - d - m*(1+rho) ]
```

So the two failure modes add a single **combined effective drop rate**

```
d_eff = d + m*(1 + rho)
```

and, for a non-dominant bot, the prize factor is

```
prize factor = ( max(0, 1 - d - m*(1 + rho)) )**2
```

This reduces **exactly** to `drop_cost` when `m = 0` and to `misread_cost` when
`d = 0` (the tests assert both across a grid). Two consequences:

1. **Adding either failure mode to the other is strictly worse** — the factor drops
   below both the drop-only `(1-d)**2` and the misread-only `(1-m(1+rho))**2`.
2. **A tool that already drops has less room to misread.** For a fixed drop rate
   `d`, the misread rate that zeros the entry falls from `1/(1+rho)` to
   `(1 - d)/(1 + rho)`.

## Tied to the corpus tallies

`from_corpus_tally(correct, miss, false_pos, correct_reject, rho)` maps a tool's
reported tally to a factor: drop rate = `miss/total`, misread rate =
`false_pos/total`. For Metaculus's own `forecasting-tools` on the binary leg
(`13 / 3 / 2 / 2`), at `rho = 3`:

| quantity | value |
|---|---|
| drop rate `d` = 3/20 | 0.15 |
| misread rate `m` = 2/20 | 0.10 |
| effective drop `d + m(1+rho)` | 0.55 |
| prize factor | **0.2025** |
| prize loss | **79.75%** |

For `mv2-forecaster` on the same leg (`14 / 2 / 0 / 4`), `m = 0`, so the factor is
the pure-drop `(1 - 0.10)**2 = 0.81`: its label-gating trades recall for **zero**
misread risk, and the combined model shows exactly what that trade is worth.

**Honest limit:** these corpora are *designed probe cases* (chosen to exercise
answer formats), so `d` and `m` from a tally are an illustrative mapping on that
probe set, **not** a natural question-stream frequency, and `rho` is a scenario.
The point is the structure — how the two blind spots combine — not a forecast of
any tool's real-world prize.

## Reproduce / verify

`test_combined_cost.py` recomputes every number offline (pure stdlib,
deterministic): the `d + m(1+rho)` effective rate and its `(max(0, …))**2` factor,
the exact reductions to `drop_cost` and `misread_cost`, the "strictly worse"
inequalities, the `(1-d)/(1+rho)` zeroing rate, the `forecasting-tools` and
`mv2-forecaster` tallies above, and a Monte Carlo over a 300-bot pool (mixing
disjoint drop and misread sets) that tracks the factor for a non-dominant bot. The
publish lane runs it before committing.

## Prior art

`drop_cost.py` and `misread_cost.py` (this repo) priced each failure mode alone.
No prior work we can find combines a forecasting-bot extractor's **drop** and
**misread** rates into one square-of-sum prize factor, shows the single effective
drop rate `d + m(1+rho)`, or maps a tool's labeled answer-format tally directly to
that factor.
