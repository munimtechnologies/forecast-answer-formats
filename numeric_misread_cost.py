"""
numeric_misread_cost.py -- What does a NUMERIC misread cost in the Metaculus
FutureEval bot tournament, and when is it worse than simply dropping the answer?

Part of forecast-answer-formats
(https://github.com/munimtechnologies/forecast-answer-formats).
Made with AI, by MV2 of Munim, Inc. Apache-2.0.

Companion to drop_cost.py and misread_cost.py. Those price a BINARY misread, where
the extractor reads the wrong probability and the penalty L is a free scenario
parameter. This module prices a NUMERIC/continuous misread -- the extractor reads
the wrong NUMBER out of a continuous forecast (drops a unit, reads "2 million" as
"2.0", grabs a figure from the reasoning, takes the wrong one of several
percentiles) -- where the penalty is NOT free: it is fixed by the geometry of the
continuous log score and the size of the misread, measured in standard deviations.

This repo's numeric corpus (xtool_numeric_formats.json) shows numeric misreads
really happen: a deployed extractor can read a line-anchored base-rate block as
the forecast. The question here is what that costs once it does.

Scoring rule (Metaculus, "Introducing Simpler, Fairer Tournament Scores"):
Total Score S = SUM of per-question Peer scores; an unforecast question is 0; the
Peer score is my log score minus the mean log score of the field. Prize share ~
max(S, 0)**2; negative totals win nothing; prizes under $50 are not paid. For a
continuous question the log score is the natural log of the predictive DENSITY at
the realized outcome.

Main result, derived and checked below.
Model the bot's intended (correctly read) forecast on a numeric question as a
predictive density centred at c0 with scale sigma, and suppose it is calibrated,
so the outcome x is drawn from that density. A misread submits the SAME shape but
centred at a wrong value c1, displaced by

    z = (c1 - c0) / sigma        (the misread displacement, in sigma units).

For a Gaussian predictive density the extra log-score loss of the misread,
averaged over the calibrated outcome, is EXACTLY

    Delta(z) = 0.5 * z**2         (nats),

independent of sigma. (Derivation in the docstring of numeric_misread_loss.) So
unlike the binary case the penalty is not a free parameter -- it is set by how far,
in standard deviations, the misread moves the forecast.

Writing mu for the per-question peer edge a correct read would earn, one numeric
misread removes that +mu AND loses Delta(z) of log score, so its peer score is

    mu - Delta(z) = mu - 0.5 * z**2,

and it costs, relative to a correct read, Delta(z) = 0.5*z**2 of Total Score --
i.e. it behaves like

    k(z) = Delta(z) / mu = z**2 / (2*mu)      effective drops.

This is the SAME "effective drops per event" law as the binary misread, where
k = 1 + rho with rho = L/mu; both are k = (log-score loss relative to a correct
read) / mu. The binary and numeric legs are two instances of one rule.

Three consequences a drop does NOT have, and the binary leg could not pin down:
  * BREAK-EVEN DISPLACEMENT. A misread is worse than a DROP (peer below 0) once
    0.5*z**2 > mu, i.e. once

        z > z* = sqrt(2*mu).

    Tournament edges are small (mu of order 0.02-0.1 nat), so z* is only about
    0.2-0.45 sigma: ANY numeric misread that moves the forecast more than a small
    fraction of a standard deviation is already worse than giving no answer at all.
  * UNIT / MAGNITUDE misreads are catastrophic. Reading "2 million" as "2.0" moves
    the centre by many sigma (z of order several), so k = z**2/(2*mu) is in the
    hundreds: one such misread can wipe out the edge of hundreds of good forecasts.
  * A misread rate m zeros the entry (prize 0, not merely smaller) once
    m*k(z) >= 1, i.e. above the zeroing rate 2*mu / z**2.

Honesty: the 0.5*z**2 law is exact for a Gaussian predictive density and is the
leading term for any smooth density (it is 0.5 * z**2 * (sigma**2 * I), with I the
Fisher information of the shape; = 0.5*z**2 for a Gaussian). The (1 - d - m*k)**2
prize law is exact for the SUM-then-SQUARE rule when one bot does not move the
pool's denominator (any non-dominant entrant). z and m are scenario inputs, not
measured frequencies; misreads may be correlated with a format family. The Monte
Carlo below draws calibrated outcomes and confirms both the 0.5*z**2 loss and the
prize factor for a non-dominant bot, making the assumptions explicit.
"""

from __future__ import annotations

import math
import random
from statistics import mean
from typing import Dict, List

_LOG_2PI = math.log(2.0 * math.pi)


def gaussian_log_score(center: float, sigma: float, outcome: float) -> float:
    """Natural-log score of a Gaussian predictive density N(center, sigma**2) at a
    realized continuous `outcome`: log of the density there. Always <= a maximum of
    -log(sigma) - 0.5*log(2*pi); higher (less negative) is better."""
    if sigma <= 0.0:
        raise ValueError("sigma must be > 0")
    z = (outcome - center) / sigma
    return -0.5 * z * z - math.log(sigma) - 0.5 * _LOG_2PI


def numeric_misread_loss(z: float) -> float:
    """Expected extra log-score loss of a numeric misread that displaces the
    forecast centre by `z` standard deviations, for a calibrated Gaussian forecast:

        E_x[ logp(x | c0) - logp(x | c0 + z*sigma) ]  =  0.5 * z**2   (nats).

    Derivation: with x = c0 + sigma*g (g ~ N(0,1)) the realized loss is
    0.5*[(x-c1)**2 - (x-c0)**2]/sigma**2 = 0.5*z**2 - z*g; taking E[g]=0 leaves
    0.5*z**2. Independent of sigma and of the sign of z."""
    return 0.5 * z * z


def numeric_misread_peer(mu: float, z: float) -> float:
    """Peer score of a numeric misread: the +mu a correct read would earn, minus
    the misread's log-score loss 0.5*z**2. Positive (still beats the field) for a
    small displacement, negative (worse than a drop's 0) once z > sqrt(2*mu)."""
    return mu - numeric_misread_loss(z)


def effective_drops_per_misread(z: float, mu: float) -> float:
    """How many silent DROPS one numeric misread of displacement z is worth in
    Total Score: k = 0.5*z**2 / mu = z**2 / (2*mu). (Binary analogue: k = 1+rho.)"""
    if mu <= 0.0:
        raise ValueError("mu must be > 0")
    return numeric_misread_loss(z) / mu


def break_even_displacement(mu: float) -> float:
    """The displacement z* = sqrt(2*mu) at which a numeric misread is exactly as
    costly as a DROP (its peer score hits 0). Beyond z* a misread is worse than
    giving no answer at all. Small when mu is small, as tournament edges are."""
    if mu <= 0.0:
        raise ValueError("mu must be > 0")
    return math.sqrt(2.0 * mu)


def effective_drop_rate(misread_rate: float, z: float, mu: float) -> float:
    """The silent-drop rate that would do the same Total-Score damage as a numeric
    misread rate `misread_rate` at displacement z: m * k(z). May exceed 1 (Total
    Score goes negative)."""
    if not 0.0 <= misread_rate <= 1.0:
        raise ValueError("misread_rate must be in [0, 1]")
    return misread_rate * effective_drops_per_misread(z, mu)


def numeric_misread_factor(misread_rate: float, z: float, mu: float) -> float:
    """Prize factor a non-dominant bot keeps under a numeric misread rate m at
    displacement z: (max(0, 1 - m*k(z)))**2, k(z) = z**2/(2*mu). Zero once
    m*k(z) >= 1 (the Total Score is non-positive and the entry wins nothing)."""
    core = 1.0 - effective_drop_rate(misread_rate, z, mu)
    return max(0.0, core) ** 2


def combined_factor(drop_rate: float, misread_rate: float, z: float, mu: float) -> float:
    """Prize factor under BOTH a silent-drop rate d and a numeric misread rate m at
    displacement z: (max(0, 1 - d - m*k(z)))**2. Reduces to drop_cost's (1-d)**2
    when m=0 and to numeric_misread_factor when d=0."""
    if not 0.0 <= drop_rate <= 1.0:
        raise ValueError("drop_rate must be in [0, 1]")
    core = 1.0 - drop_rate - effective_drop_rate(misread_rate, z, mu)
    return max(0.0, core) ** 2


def zeroing_misread_rate(z: float, mu: float, drop_rate: float = 0.0) -> float:
    """The numeric misread rate at which the Total Score hits 0 (prize -> 0):
    (1 - d) / k(z) = (1 - d) * 2*mu / z**2. Above it the entry wins nothing."""
    if not 0.0 <= drop_rate <= 1.0:
        raise ValueError("drop_rate must be in [0, 1]")
    k = effective_drops_per_misread(z, mu)
    if k <= 0.0:
        return float("inf")
    return (1.0 - drop_rate) / k


def unit_misread_scenario(
    true_center: float = 2.0e6,
    read_center: float = 2.0,
    sigma: float = 1.0e6,
    mu: float = 0.03,
) -> Dict[str, float]:
    """A concrete magnitude misread: the model's forecast is centred at 2 million
    with a 1-million scale, but the extractor drops the unit and reads "2.0". The
    displacement is z = (2 - 2e6)/1e6 ~ -2 sigma. Returns z, the log-score loss,
    the effective drops, the misread peer, and the zeroing rate -- showing a single
    magnitude misread costs tens of dropped answers even at a modest 2-sigma miss,
    and far more for a true unit error (z of order several)."""
    z = (read_center - true_center) / sigma
    return {
        "z": z,
        "loss_nats": numeric_misread_loss(z),
        "effective_drops": effective_drops_per_misread(z, mu),
        "misread_peer": numeric_misread_peer(mu, z),
        "break_even_z": break_even_displacement(mu),
        "zeroing_misread_rate": zeroing_misread_rate(z, mu),
    }


def simulate_loss(z: float, sigma: float = 1.0, trials: int = 200000, seed: int = 0) -> float:
    """Monte Carlo check that the expected log-score loss of a z-sigma misread is
    0.5*z**2: draw calibrated outcomes x ~ N(0, sigma**2) and average
    gaussian_log_score(0,...) - gaussian_log_score(z*sigma,...)."""
    rng = random.Random(seed)
    c1 = z * sigma
    tot = 0.0
    for _ in range(trials):
        x = rng.gauss(0.0, sigma)
        tot += gaussian_log_score(0.0, sigma, x) - gaussian_log_score(c1, sigma, x)
    return tot / trials


def simulate_share_ratio(
    misread_rate: float,
    z: float,
    n_questions: int = 200,
    n_bots: int = 300,
    mu: float = 0.03,
    sigma_target: float = 0.03,
    sigma_field: float = 0.15,
    trials: int = 400,
    seed: int = 0,
) -> float:
    """Monte Carlo check that a non-dominant bot's prize share scales as
    (max(0, 1 - m*k(z)))**2 under a numeric misread rate m at displacement z.

    Each trial draws the target's per-question correct-read edges gauss(mu,
    sigma_target); for a random round(m*n) of them it subtracts a realized misread
    loss 0.5*z**2 - z*g (g ~ N(0,1)), whose mean is the analytic 0.5*z**2. It
    recomputes the target's Total Score and its prize share (max(S,0)**2 normalized)
    against a field of gauss(0, sigma_field*sqrt(n)) bots and returns the mean over
    trials of share_with_misreads / share_without."""
    rng = random.Random(seed)
    k = round(misread_rate * n_questions)
    base = 0.5 * z * z
    ratios: List[float] = []
    for _ in range(trials):
        edges = [rng.gauss(mu, sigma_target) for _ in range(n_questions)]
        others = [
            rng.gauss(0.0, sigma_field * math.sqrt(n_questions))
            for _ in range(n_bots - 1)
        ]
        s0 = sum(edges)
        mis_idx = set(rng.sample(range(n_questions), k)) if k else set()
        sm = 0.0
        for i, e in enumerate(edges):
            if i in mis_idx:
                sm += e - (base - z * rng.gauss(0.0, 1.0))
            else:
                sm += e
        share0 = _share(s0, [s0] + others)
        sharem = _share(sm, [sm] + others)
        if share0 > 0.0:
            ratios.append(sharem / share0)
    return mean(ratios) if ratios else 0.0


def _share(my_total: float, all_totals: List[float]) -> float:
    pos = [max(t, 0.0) ** 2 for t in all_totals]
    denom = sum(pos)
    if denom <= 0.0:
        return 0.0
    return (max(my_total, 0.0) ** 2) / denom


def _demo() -> None:
    print("Cost of a NUMERIC misread in a square-of-sum tournament")
    print("(wrong number read out of a continuous forecast -> log-score loss 0.5*z^2)\n")
    for mu in (0.02, 0.05, 0.10):
        print(f"edge mu = {mu:.2f}:  break-even displacement z* = "
              f"{break_even_displacement(mu):.3f} sigma "
              f"(beyond this a misread is worse than a drop)")
    print()
    mu = 0.03
    print(f"Effective drops and prize factor vs displacement z (mu = {mu:.2f}, "
          f"misread rate m = 5%):")
    print(f"{'z':>5}  {'loss':>7}  {'k=drops':>8}  {'peer':>8}  {'factor':>8}  {'MC':>8}")
    for z in (0.2, 0.5, 1.0, 2.0, 4.0):
        print(
            f"{z:>5.1f}  {numeric_misread_loss(z):>7.3f}  "
            f"{effective_drops_per_misread(z, mu):>8.2f}  "
            f"{numeric_misread_peer(mu, z):>8.4f}  "
            f"{numeric_misread_factor(0.05, z, mu):>8.4f}  "
            f"{simulate_share_ratio(0.05, z, mu=mu):>8.4f}"
        )
    sc = unit_misread_scenario()
    print(f"\nMagnitude misread (2e6 read as 2.0, sigma 1e6): z = {sc['z']:.2f}, "
          f"loss {sc['loss_nats']:.2f} nats = {sc['effective_drops']:.0f} drops.")
    print("A single unit/magnitude misread can erase the edge of hundreds of "
          "good forecasts.")


if __name__ == "__main__":
    _demo()
