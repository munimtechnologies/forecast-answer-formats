"""
drop_cost.py -- What does a silently dropped answer cost in the Metaculus
FutureEval bot tournament?

Part of forecast-answer-formats
(https://github.com/munimtechnologies/forecast-answer-formats).
Made with AI, by MV2 of Munim, Inc. Apache-2.0.

The sibling corpora in this repo measure WHICH valid LLM answer formats two
deployed forecasting-bot extractors -- mv2-forecaster and Metaculus's
`forecasting-tools` -- silently drop (return nothing) or misread. This module
answers the next question: given a silent-drop rate d, what does it cost in the
tournament prize?

Tournament rule (Metaculus, "Introducing Simpler, Fairer Tournament Scores"):
a forecaster's Total Score S is the SUM of their per-question Peer scores -- and
a question you never forecast contributes 0 to that sum. Prize share is
proportional to S**2 (negative totals win nothing; prizes under $50 are not
paid). The Peer score of a forecast is its log score minus the mean log score of
the other forecasters on the same question, so it is positive exactly when the
forecast beats the field.

Main result, derived and checked below:
  If a bot would earn a positive mean peer score mu on each question it genuinely
  forecasts over N questions, its Total Score is N*mu. If a fraction d of its
  answers are silently dropped, those become zeros, so its Total Score falls to
  (1-d)*N*mu. Because the prize share is proportional to S**2, the prize falls by
  the factor (1-d)**2 -- NOT (1-d). For small d that is a ~2d loss:

      payout factor   loss
  d   (1-d)**2        1-(1-d)**2
  --  --------        ----------
  5%  0.9025          9.75%
  10% 0.8100          19.00%
  15% 0.7225          27.75%
  20% 0.6400          36.00%
  30% 0.4900          51.00%

  A silently dropped answer is about twice as expensive as its raw rate, and the
  $50 floor can turn a near-threshold entry's loss into 100%. This is why an
  extractor that drops a whole answer-format family (see this repo's corpora) is
  a first-order tournament risk, not a cosmetic one.

Honesty: the (1-d)**2 law is exact for the SUM-then-SQUARE scoring rule when one
bot's drop does not materially change the pool's denominator (true for any
non-dominant entrant). Per-question peer scores vary, drops may be correlated
with format rather than random, and real pools are finite; the Monte Carlo below
confirms the law holds for a non-dominant bot in a realistic pool and makes those
assumptions explicit.
"""

from __future__ import annotations

import math
import random
from statistics import mean
from typing import Dict, Iterable, List, Sequence

# Clamp probabilities away from 0/1 so the natural log never diverges; mirrors
# how platforms bound forecasts before scoring.
_EPS = 1e-9


def log_score(p: float, outcome: int) -> float:
    """Natural-log score of a binary forecast p for a realized outcome in {0,1}.

    Always <= 0; 0 is a perfect forecast. Metaculus's peer score is built on this
    log score (it reports a scaled version, but peer *differences* are invariant
    to a shared positive scale, so the ratios computed here are unchanged).
    """
    if outcome not in (0, 1):
        raise ValueError("outcome must be 0 or 1")
    p = min(max(p, _EPS), 1.0 - _EPS)
    return math.log(p) if outcome == 1 else math.log(1.0 - p)


def peer_score(my_p: float, others_p: Sequence[float], outcome: int) -> float:
    """Peer score of my forecast vs. the other forecasters on one question.

    = my log score - mean(other forecasters' log scores). Positive iff I beat the
    field. With no other forecasters the peer score is 0 (undefined field).
    """
    if not others_p:
        return 0.0
    field = mean(log_score(q, outcome) for q in others_p)
    return log_score(my_p, outcome) - field


def total_score(peers: Iterable[float]) -> float:
    """Total Score = sum of per-question peer scores. Unforecast questions are 0,
    so simply omit them (or pass 0.0) -- both give the same sum."""
    return float(sum(peers))


def prize_share(my_total: float, all_totals: Sequence[float]) -> float:
    """Share of the prize pool: max(my_total,0)**2 / sum of max(t,0)**2 over all
    entrants. Negative totals win nothing and are excluded from the denominator."""
    pos = [max(t, 0.0) ** 2 for t in all_totals]
    denom = sum(pos)
    if denom <= 0.0:
        return 0.0
    return (max(my_total, 0.0) ** 2) / denom


def expected_payout_factor(drop_rate: float) -> float:
    """The analytic prize factor from a silent-drop rate d: (1-d)**2.

    This is the fraction of the no-drop prize a non-dominant bot keeps when a
    fraction d of its answers are silently dropped (each dropped answer -> peer 0,
    Total Score scales by (1-d), prize ~ Total Score**2)."""
    if not 0.0 <= drop_rate <= 1.0:
        raise ValueError("drop_rate must be in [0, 1]")
    return (1.0 - drop_rate) ** 2


def payout_loss(drop_rate: float) -> float:
    """Fraction of the prize LOST to a silent-drop rate d: 1 - (1-d)**2.

    Always exceeds d for 0 < d < 1 (silent drops are convex-costly)."""
    return 1.0 - expected_payout_factor(drop_rate)


def payout_factor_table(
    drop_rates: Sequence[float] = (0.05, 0.10, 0.15, 0.20, 0.30),
) -> Dict[float, Dict[str, float]]:
    """Convenience table of {d: {'payout_factor': (1-d)**2, 'loss': 1-(1-d)**2}}.

    Illustrative use: if a format family that YOUR extractor drops makes up a
    fraction d of your model's final answers (this repo's corpora show which
    families each tool drops), this is the resulting prize factor. The corpora are
    designed probes, not a frequency estimate, so treat d as a scenario, not a
    measured rate."""
    return {
        d: {"payout_factor": expected_payout_factor(d), "loss": payout_loss(d)}
        for d in drop_rates
    }


def paid_after_floor(
    prize_pool: float, share: float, floor: float = 50.0
) -> float:
    """Amount actually paid given a prize pool and a computed share, applying the
    Metaculus rule that prizes under `floor` (default $50) are not paid."""
    amount = prize_pool * share
    return amount if amount >= floor else 0.0


def simulate_share_ratio(
    drop_rate: float,
    n_questions: int = 200,
    n_bots: int = 300,
    mu: float = 0.02,
    sigma_target: float = 0.03,
    sigma_field: float = 0.15,
    trials: int = 500,
    seed: int = 0,
) -> float:
    """Monte Carlo check that a non-dominant bot's prize share scales as (1-d)**2.

    Each trial builds a pool of `n_bots`: one target bot whose per-question peer
    scores are gauss(mu, sigma_target) (mean advantage mu over the field), and
    `n_bots-1` field bots whose totals are gauss(0, sigma_field*sqrt(n)). We drop a
    random `round(d*n_questions)` of the target's answers (-> 0), recompute its
    Total Score and prize share, and return the mean over trials of
    share_with_drops / share_without_drops. For a non-dominant bot this tracks
    (1-d)**2.
    """
    rng = random.Random(seed)
    k = round(drop_rate * n_questions)
    ratios: List[float] = []
    for _ in range(trials):
        target_peers = [rng.gauss(mu, sigma_target) for _ in range(n_questions)]
        others_totals = [
            rng.gauss(0.0, sigma_field * math.sqrt(n_questions))
            for _ in range(n_bots - 1)
        ]
        s0 = sum(target_peers)
        drop_idx = set(rng.sample(range(n_questions), k)) if k else set()
        sd = sum(p for i, p in enumerate(target_peers) if i not in drop_idx)
        share0 = prize_share(s0, [s0] + others_totals)
        shared = prize_share(sd, [sd] + others_totals)
        if share0 > 0.0:
            ratios.append(shared / share0)
    return mean(ratios) if ratios else 0.0


def _demo() -> None:
    print("Cost of a silent answer-drop in a square-of-sum tournament")
    print("(prize ~ (sum of peer scores)**2; an unforecast question is a 0)\n")
    print(f"{'drop d':>7}  {'(1-d)^2':>8}  {'prize loss':>10}  {'MC ratio':>9}")
    for d in (0.05, 0.10, 0.15, 0.20, 0.30):
        mc = simulate_share_ratio(d)
        print(
            f"{d:>6.0%}  {expected_payout_factor(d):>8.4f}  "
            f"{payout_loss(d):>9.2%}  {mc:>9.4f}"
        )
    print(
        "\nA drop costs ~2x its raw rate because prize ~ score**2. Plus the $50 "
        "floor can zero a near-threshold entry entirely."
    )


if __name__ == "__main__":
    _demo()
