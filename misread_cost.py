"""
misread_cost.py -- What does a silent MISREAD cost in the Metaculus FutureEval
bot tournament, and how does it compare to a silent drop?

Part of forecast-answer-formats
(https://github.com/munimtechnologies/forecast-answer-formats).
Made with AI, by MV2 of Munim, Inc. Apache-2.0.

Companion to drop_cost.py. A *drop* is when the extractor returns nothing, so the
question contributes 0 to the Total Score. A *misread* is worse: the extractor
returns a number that was never the model's forecast -- a base rate it read in
passing, a figure from the reasoning, the wrong one of several percentages. The
bot then posts a CONFIDENT WRONG forecast, which earns a large NEGATIVE peer score
on that question instead of the positive edge a correct forecast would have had.
This repo's corpora show both failure modes really happen: e.g. forecasting-tools
can read a labeled base rate ("...a 5% base rate...") as the forecast (a false
positive), which is a misread, not a drop.

Scoring rule (Metaculus, "Introducing Simpler, Fairer Tournament Scores"):
Total Score S = SUM of per-question Peer scores; an unforecast question is 0; the
Peer score is my log score minus the mean log score of the field, so it is
positive exactly when I beat the field. Prize share ~ max(S, 0)**2; negative
totals win nothing; prizes under $50 are not paid.

Main result, derived and checked below.
Let a bot forecast N questions, earning mean peer edge mu > 0 on each question it
reads correctly. Define the MISREAD PENALTY L > 0 as the magnitude of the
(negative) peer score of a confident wrong forecast, and the penalty-to-edge ratio

    rho = L / mu.

A drop replaces a +mu with 0, costing mu of Total Score. A misread replaces a +mu
with -L, costing mu + L = mu*(1 + rho) of Total Score. So, PER EVENT, a misread is

    (1 + rho) times as costly to the Total Score as a drop.

If a fraction m of answers are misread (and the rest earn +mu), then
    S = N*mu * (1 - m*(1 + rho)),
so a misread rate m acts like an *effective drop rate* m*(1 + rho), and the prize
factor is

    (max(0, 1 - m*(1 + rho)))**2.

Two qualitative consequences a pure drop does NOT have:
  * Because rho is typically several (a confident wrong forecast is punished far
    harder by the log score than a single good forecast is rewarded), a handful of
    misreads can erase the edge of many good forecasts.
  * The Total Score itself can go NEGATIVE -- and then the prize is 0, not merely
    smaller -- once m exceeds the ZEROING RATE 1/(1 + rho) < 1. A drop only zeros
    the prize in the limit d -> 1.

Honesty: the law is exact for the SUM-then-SQUARE rule when one bot does not move
the pool's denominator (any non-dominant entrant). rho depends on how confident
and how wrong the misread is and on the field; it is a scenario, not a measured
frequency. Misreads may be correlated with a format family rather than random.
The worked scenario and the Monte Carlo below make the assumptions explicit.
"""

from __future__ import annotations

import math
import random
from statistics import mean
from typing import Dict, List, Sequence

import drop_cost as dc


def misread_peer(wrong_p: float, field_p: float, outcome: int) -> float:
    """Peer score of a confident WRONG forecast `wrong_p` against a field that
    forecast `field_p`, for the realized `outcome`. Normally negative: the misread
    posts a number that loses to the field."""
    return dc.peer_score(wrong_p, [field_p], outcome)


def miss_penalty(wrong_p: float, field_p: float, outcome: int) -> float:
    """The misread penalty L = -(peer score of the wrong forecast), i.e. how many
    peer-score points a single confident misread subtracts from the Total Score.
    L > 0 exactly when the misread loses to the field (the usual case)."""
    return -misread_peer(wrong_p, field_p, outcome)


def penalty_to_edge_ratio(
    good_p: float, wrong_p: float, field_p: float, outcome: int
) -> float:
    """rho = L / mu for one worked question: the misread penalty L divided by the
    peer edge mu the bot WOULD have earned had it read its good forecast `good_p`.

    Requires the good forecast to actually beat the field (mu > 0), which is the
    only regime where a drop/misread represents a loss worth pricing."""
    mu = dc.peer_score(good_p, [field_p], outcome)
    if mu <= 0.0:
        raise ValueError("good_p must beat the field (mu > 0) to define rho")
    return miss_penalty(wrong_p, field_p, outcome) / mu


def per_event_cost_ratio(rho: float) -> float:
    """How many times as costly to the Total Score ONE misread is versus ONE drop:
    a drop forgoes mu; a misread forgoes mu AND adds L, i.e. mu*(1+rho). So the
    ratio is simply (1 + rho)."""
    if rho < 0.0:
        raise ValueError("rho must be >= 0")
    return 1.0 + rho


def effective_drop_rate(misread_rate: float, rho: float) -> float:
    """The drop rate that would do the same damage to the Total Score as a misread
    rate `misread_rate`: m*(1 + rho). Can exceed 1 (meaning the Total Score goes
    negative)."""
    if not 0.0 <= misread_rate <= 1.0:
        raise ValueError("misread_rate must be in [0, 1]")
    if rho < 0.0:
        raise ValueError("rho must be >= 0")
    return misread_rate * (1.0 + rho)


def misread_payout_factor(misread_rate: float, rho: float) -> float:
    """Prize factor a non-dominant bot keeps under a misread rate m and
    penalty/edge ratio rho: (max(0, 1 - m*(1+rho)))**2.

    Once m*(1+rho) >= 1 the Total Score is <= 0 and the factor is 0 (the entry
    wins nothing), not merely small."""
    core = 1.0 - effective_drop_rate(misread_rate, rho)
    return max(0.0, core) ** 2


def misread_payout_loss(misread_rate: float, rho: float) -> float:
    """Fraction of the no-error prize LOST to a misread rate m: 1 - factor."""
    return 1.0 - misread_payout_factor(misread_rate, rho)


def zeroing_misread_rate(rho: float) -> float:
    """The misread rate at which the Total Score hits 0 (prize -> 0): 1/(1+rho).
    Below this the entry still scores positive; above it, it wins nothing."""
    if rho < 0.0:
        raise ValueError("rho must be >= 0")
    return 1.0 / (1.0 + rho)


def base_rate_misread_scenario() -> Dict[str, float]:
    """A concrete, first-principles worked example of a misread this repo's corpora
    actually produce: on a binary question that resolves YES, the field forecasts
    0.60, the bot's good forecast would be 0.90, but its extractor reads a labeled
    "5% base rate" from the reasoning as the forecast (0.05). Returns the resulting
    mu, L, rho, per-event cost ratio vs a drop, and the zeroing misread rate.

    All numbers follow from the log/peer definitions in drop_cost.py; nothing is
    tuned. They show the qualitative point: because the log score punishes a
    confident wrong answer far harder than it rewards one good answer, a single
    misread here costs about as much Total Score as ~7 dropped answers, and a
    misread rate near 14% would zero this bot's entry."""
    field_p, good_p, wrong_p, outcome = 0.60, 0.90, 0.05, 1
    mu = dc.peer_score(good_p, [field_p], outcome)
    L = miss_penalty(wrong_p, field_p, outcome)
    rho = L / mu
    return {
        "field_p": field_p,
        "good_p": good_p,
        "wrong_p": wrong_p,
        "mu": mu,
        "L": L,
        "rho": rho,
        "per_event_vs_drop": per_event_cost_ratio(rho),
        "zeroing_misread_rate": zeroing_misread_rate(rho),
    }


def simulate_misread_share_ratio(
    misread_rate: float,
    rho: float,
    n_questions: int = 200,
    n_bots: int = 300,
    mu: float = 0.02,
    sigma_target: float = 0.03,
    sigma_pen: float = 0.03,
    sigma_field: float = 0.15,
    trials: int = 500,
    seed: int = 0,
) -> float:
    """Monte Carlo check that a non-dominant bot's prize share scales as
    (max(0, 1 - m*(1+rho)))**2 under a misread rate m.

    Each trial draws the target bot's per-question edges gauss(mu, sigma_target),
    then replaces a random round(m*n) of them with a misread peer drawn
    gauss(-rho*mu, sigma_pen) (penalty L = rho*mu). We recompute the target's Total
    Score and prize share against a field of gauss(0, sigma_field*sqrt(n)) bots and
    return the mean over trials of share_with_misreads / share_without."""
    rng = random.Random(seed)
    k = round(misread_rate * n_questions)
    L = rho * mu
    ratios: List[float] = []
    for _ in range(trials):
        edges = [rng.gauss(mu, sigma_target) for _ in range(n_questions)]
        others_totals = [
            rng.gauss(0.0, sigma_field * math.sqrt(n_questions))
            for _ in range(n_bots - 1)
        ]
        s0 = sum(edges)
        mis_idx = set(rng.sample(range(n_questions), k)) if k else set()
        sm = sum(
            (rng.gauss(-L, sigma_pen) if i in mis_idx else e)
            for i, e in enumerate(edges)
        )
        share0 = dc.prize_share(s0, [s0] + others_totals)
        sharem = dc.prize_share(sm, [sm] + others_totals)
        if share0 > 0.0:
            ratios.append(sharem / share0)
    return mean(ratios) if ratios else 0.0


def _demo() -> None:
    sc = base_rate_misread_scenario()
    print("Cost of a silent MISREAD in a square-of-sum tournament")
    print("(a confident wrong forecast -> a NEGATIVE peer score, not a 0)\n")
    print("Worked scenario: binary resolves YES, field 0.60, good forecast 0.90,")
    print("extractor misreads a '5% base rate' as the forecast (0.05):")
    print(f"  per-question edge  mu  = {sc['mu']:.4f}")
    print(f"  misread penalty    L   = {sc['L']:.4f}")
    print(f"  ratio              rho = {sc['rho']:.2f}")
    print(f"  one misread costs as much Total Score as {sc['per_event_vs_drop']:.1f} drops")
    print(f"  a misread rate of {sc['zeroing_misread_rate']:.1%} zeros this entry\n")
    rho = 3.0
    print(f"Prize factor vs misread rate m (rho = {rho:.0f}):")
    print(f"{'m':>5}  {'eff drop':>9}  {'factor':>8}  {'loss':>7}  {'MC':>7}")
    for m in (0.02, 0.05, 0.10, 0.20, 0.30):
        print(
            f"{m:>5.0%}  {effective_drop_rate(m, rho):>9.2f}  "
            f"{misread_payout_factor(m, rho):>8.4f}  "
            f"{misread_payout_loss(m, rho):>6.1%}  "
            f"{simulate_misread_share_ratio(m, rho):>7.4f}"
        )
    print(
        f"\nZeroing rate 1/(1+rho) = {zeroing_misread_rate(rho):.1%}: above it the "
        "Total Score is negative and the entry wins nothing."
    )


if __name__ == "__main__":
    _demo()
