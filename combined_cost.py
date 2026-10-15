"""
combined_cost.py -- What do silent drops AND misreads cost TOGETHER in the
Metaculus FutureEval bot tournament, and how do a tool's measured corpus tallies
map to a prize factor?

Part of forecast-answer-formats
(https://github.com/munimtechnologies/forecast-answer-formats).
Made with AI, by MV2 of Munim, Inc. Apache-2.0.

drop_cost.py priced a silent DROP (extractor returns nothing -> peer 0): prize
factor (1-d)**2. misread_cost.py priced a silent MISREAD (extractor returns a
number that was never the forecast -> confident wrong forecast -> NEGATIVE peer
-L): prize factor (max(0, 1 - m*(1+rho)))**2, where rho = L/mu. A real extractor
does BOTH -- this repo's cross-tool corpora report, per tool, how many answerable
cases it DROPS (a "miss") and how many it MISREADS (a "false positive"). This
module combines the two failure modes into one prize factor and ties it straight
to those tallies.

Scoring rule (unchanged): Total Score S = SUM of per-question peer scores; an
unforecast question is 0; prize share ~ max(S, 0)**2; negative totals win
nothing; prizes under $50 are not paid.

Main result, derived and checked below.
On each of N questions a bot either (a) reads its answer correctly and earns a
mean peer edge mu > 0, (b) drops it (peer 0), or (c) misreads it (peer -L, with
rho = L/mu). With a drop rate d and a misread rate m (d + m <= 1),

    S = N*mu * [ (1 - d - m) - m*rho ]
      = N*mu * [ 1 - d - m*(1 + rho) ].

So drops and misreads add a single COMBINED effective drop rate

    d_eff = d + m*(1 + rho),

and, for a non-dominant bot, the prize factor is

    (max(0, 1 - d - m*(1 + rho)))**2.

It reduces exactly to drop_cost when m = 0 ( (1-d)**2 ) and to misread_cost when
d = 0 ( (max(0, 1 - m*(1+rho)))**2 ), and the entry is ZEROED -- wins nothing --
once d + m*(1 + rho) >= 1. For a fixed drop rate d the zeroing misread rate falls
to (1 - d)/(1 + rho): a tool that already drops some answers has even less room
to misread before it scores nothing.

Honesty: same regime as the siblings -- exact for the sum-then-square rule when
one bot does not move the pool's denominator; rho is a scenario, not a measured
frequency; drops/misreads may be correlated with a format family. The corpus
tallies are from DESIGNED probe cases (which formats each tool reads), so the
rates from from_corpus_tally are an illustrative mapping on that probe set, not a
natural field frequency. The Monte Carlo below makes the assumptions explicit.
"""

from __future__ import annotations

import math
import random
from statistics import mean
from typing import Dict, List

import drop_cost as dc
import misread_cost as mc


def combined_effective_drop_rate(drop_rate: float, misread_rate: float, rho: float) -> float:
    """The single effective drop rate that drops at rate d and misreads at rate m
    (penalty/edge ratio rho) are together equivalent to: d + m*(1 + rho).

    Can exceed 1, meaning the Total Score goes negative."""
    if drop_rate < 0.0 or misread_rate < 0.0:
        raise ValueError("rates must be >= 0")
    if drop_rate + misread_rate > 1.0 + 1e-12:
        raise ValueError("drop_rate + misread_rate must be <= 1")
    if rho < 0.0:
        raise ValueError("rho must be >= 0")
    return drop_rate + misread_rate * (1.0 + rho)


def combined_payout_factor(drop_rate: float, misread_rate: float, rho: float) -> float:
    """Prize factor a non-dominant bot keeps under BOTH a drop rate d and a misread
    rate m: (max(0, 1 - d - m*(1+rho)))**2.

    Once d + m*(1+rho) >= 1 the Total Score is <= 0 and the factor is 0."""
    core = 1.0 - combined_effective_drop_rate(drop_rate, misread_rate, rho)
    return max(0.0, core) ** 2


def combined_payout_loss(drop_rate: float, misread_rate: float, rho: float) -> float:
    """Fraction of the no-error prize LOST to drops and misreads together."""
    return 1.0 - combined_payout_factor(drop_rate, misread_rate, rho)


def zeroing_misread_rate_given_drop(drop_rate: float, rho: float) -> float:
    """The misread rate at which the Total Score hits 0 for a bot that ALSO drops
    at rate d: (1 - d)/(1 + rho). At d = 0 this is misread_cost's 1/(1+rho); every
    point of drop rate shrinks the misread headroom."""
    if not 0.0 <= drop_rate <= 1.0:
        raise ValueError("drop_rate must be in [0, 1]")
    if rho < 0.0:
        raise ValueError("rho must be >= 0")
    return (1.0 - drop_rate) / (1.0 + rho)


def from_corpus_tally(
    correct: int, miss: int, false_pos: int, correct_reject: int, rho: float
) -> Dict[str, float]:
    """Map a tool's cross-tool corpus tally (the correct/miss/false_pos/
    correct_reject counts this repo reports per tool) to a prize factor.

    A `miss` is a dropped answerable case (a drop); a `false_pos` is a case where
    the extractor returned a number that was not the answer (a misread). We take
    the drop rate as miss/total and the misread rate as false_pos/total over the
    labeled probe corpus, then apply combined_payout_factor at the given rho.

    IMPORTANT: this is a DESIGNED probe corpus (cases chosen to exercise answer
    formats), so d and m here are an illustrative mapping on that probe set, NOT a
    natural question-stream frequency. It shows how the two blind spots a tool has
    would combine IF they occurred at these rates."""
    total = correct + miss + false_pos + correct_reject
    if total <= 0:
        raise ValueError("tally must have at least one case")
    for n in (correct, miss, false_pos, correct_reject):
        if n < 0:
            raise ValueError("tally counts must be >= 0")
    d = miss / total
    m = false_pos / total
    return {
        "total": float(total),
        "drop_rate": d,
        "misread_rate": m,
        "effective_drop_rate": combined_effective_drop_rate(d, m, rho),
        "payout_factor": combined_payout_factor(d, m, rho),
        "payout_loss": combined_payout_loss(d, m, rho),
    }


def simulate_combined_share_ratio(
    drop_rate: float,
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
    (max(0, 1 - d - m*(1+rho)))**2 when a random fraction d of answers are dropped
    (-> 0) and a disjoint fraction m are misread (-> gauss(-rho*mu, sigma_pen))."""
    rng = random.Random(seed)
    k_d = round(drop_rate * n_questions)
    k_m = round(misread_rate * n_questions)
    if k_d + k_m > n_questions:
        raise ValueError("drop + misread counts exceed the number of questions")
    L = rho * mu
    ratios: List[float] = []
    for _ in range(trials):
        edges = [rng.gauss(mu, sigma_target) for _ in range(n_questions)]
        others_totals = [
            rng.gauss(0.0, sigma_field * math.sqrt(n_questions))
            for _ in range(n_bots - 1)
        ]
        s0 = sum(edges)
        picks = rng.sample(range(n_questions), k_d + k_m) if (k_d + k_m) else []
        drop_idx = set(picks[:k_d])
        mis_idx = set(picks[k_d:])
        sm = 0.0
        for i, e in enumerate(edges):
            if i in drop_idx:
                sm += 0.0
            elif i in mis_idx:
                sm += rng.gauss(-L, sigma_pen)
            else:
                sm += e
        share0 = dc.prize_share(s0, [s0] + others_totals)
        sharem = dc.prize_share(sm, [sm] + others_totals)
        if share0 > 0.0:
            ratios.append(sharem / share0)
    return mean(ratios) if ratios else 0.0


def _demo() -> None:
    print("Combined cost of silent drops AND misreads in a square-of-sum tournament")
    print("prize factor = (max(0, 1 - d - m*(1+rho)))**2\n")
    # The binary cross-tool tally for Metaculus's forecasting-tools: 13/3/2/2.
    rho = 3.0
    ft = from_corpus_tally(13, 3, 2, 2, rho)
    print("forecasting-tools binary tally 13/3/2/2 (correct/miss/false_pos/reject):")
    print(f"  drop rate d  = {ft['drop_rate']:.2f}   misread rate m = {ft['misread_rate']:.2f}")
    print(f"  at rho={rho:.0f}: effective drop = {ft['effective_drop_rate']:.2f}, "
          f"prize factor = {ft['payout_factor']:.4f} (loss {ft['payout_loss']:.1%})\n")
    print(f"{'d':>5}  {'m':>5}  {'eff':>5}  {'factor':>8}  {'MC':>7}")
    for d, m in ((0.10, 0.00), (0.00, 0.10), (0.10, 0.05), (0.15, 0.10), (0.10, 0.20)):
        print(
            f"{d:>5.2f}  {m:>5.2f}  {combined_effective_drop_rate(d, m, rho):>5.2f}  "
            f"{combined_payout_factor(d, m, rho):>8.4f}  "
            f"{simulate_combined_share_ratio(d, m, rho):>7.4f}"
        )
    print(
        f"\nFor d=0.10, rho={rho:.0f} the misread rate that zeros the entry is "
        f"{zeroing_misread_rate_given_drop(0.10, rho):.1%} "
        f"(vs {mc.zeroing_misread_rate(rho):.1%} with no drops)."
    )


if __name__ == "__main__":
    _demo()
