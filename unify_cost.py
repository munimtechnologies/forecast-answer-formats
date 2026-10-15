# SPDX-License-Identifier: Apache-2.0
# Part of forecast-answer-formats, by MV2 of Munim, Inc. Licensed under Apache-2.0.
"""Unified extractor-error cost law for a square-of-sum forecasting tournament.

This module consolidates the three type-specific cost models already in this
repo (``drop_cost``, ``misread_cost``, ``numeric_misread_cost``, and their
``combined_cost``) under a single law, and proves by construction that each is
an instance of it.

Setup (the Metaculus tournament rule these models price):

    Total Score  S = sum over answered questions of the per-question peer score
                     (my log score minus the mean field log score);
                     an unforecast question contributes 0.
    Prize share  proportional to  max(S, 0) ** 2.

Write ``mu`` for the bot's mean per-question peer edge (so a correct read of a
typical question contributes ``+mu`` to ``S``). An *extractor error* on a
question replaces that ``+mu`` with a smaller value; call the gap, measured in
nats of log score relative to a correct read, ``L_err``. Because every
question contributes additively to ``S``, that one error subtracts ``L_err``
from ``S`` -- exactly ``L_err / mu`` times what a single correct answer adds.
So an error costs

    k = L_err / mu

in units of *effective dropped answers*. If error channel ``i`` occurs at rate
``r_i`` with per-error loss ``L_i`` (hence ``k_i = L_i / mu``), then
``S -> S * (1 - sum_i r_i * k_i)`` and, since the prize is proportional to the
square of ``S``, the expected prize is multiplied by

    (max(0, 1 - sum_i r_i * k_i)) ** 2.

The three shipped models are the three ways an error loses log score:

    drop             L_err = mu           -> k = 1            (forgo the edge)
    binary misread   L_err = mu + L       -> k = 1 + rho      (rho = L / mu)
    numeric misread  L_err = 0.5 * z**2   -> k = z**2/(2*mu)  (z-sigma shift)

A drop lands at the no-forecast value (0), giving up the whole edge. A binary
misread posts the confident wrong answer, giving up the edge *and* paying a
penalty L. A numeric misread shifts a calibrated Gaussian's centre by z standard
deviations, whose log-score loss is exactly 0.5*z**2 nats. All three are
``k = L_err / mu``.
"""

import math


def effective_drops(log_score_loss_nats, mu):
    """Cost of one extractor error in 'effective dropped answers': ``k = L_err / mu``.

    ``log_score_loss_nats`` is the error's loss in nats of log score relative to
    a correct read; ``mu`` is the bot's mean per-question peer edge (nats).
    """
    if mu <= 0:
        raise ValueError("mu (mean per-question peer edge) must be positive")
    if log_score_loss_nats < 0:
        raise ValueError("log-score loss relative to a correct read cannot be negative")
    return log_score_loss_nats / mu


def drop_k():
    """A dropped answer forgoes the whole edge: ``L_err = mu``, so ``k = 1``."""
    return 1.0


def binary_misread_k(rho):
    """A binary misread posts a confident wrong forecast.

    It gives up the edge ``mu`` and pays a penalty ``L``, so ``L_err = mu + L``
    and, with ``rho = L / mu``, ``k = 1 + rho``.
    """
    if rho < 0:
        raise ValueError("rho = L/mu cannot be negative")
    return 1.0 + rho


def numeric_misread_k(z, mu):
    """A numeric misread shifts a Gaussian centre by ``z`` sigma.

    Its log-score loss is exactly ``0.5 * z**2`` nats, so ``k = z**2 / (2*mu)``.
    """
    if mu <= 0:
        raise ValueError("mu must be positive")
    return (z * z) / (2.0 * mu)


def break_even_displacement(mu):
    """The ``z*`` at which a numeric misread costs exactly one drop.

    Solves ``0.5 * z*^2 = mu``, i.e. ``z* = sqrt(2*mu)``. Below ``z*`` a numeric
    misread is cheaper than giving no answer; above it, costlier.
    """
    if mu <= 0:
        raise ValueError("mu must be positive")
    return math.sqrt(2.0 * mu)


def prize_factor(errors, mu):
    """Multiplicative hit to the expected prize from one or more error channels.

    ``errors`` is an iterable of ``(rate, log_score_loss_nats)`` pairs. Returns

        (max(0, 1 - sum_i rate_i * k_i)) ** 2,   k_i = loss_i / mu.

    Once the bracket would go negative the entry is zeroed, so the factor
    clamps at 0.
    """
    total = 0.0
    for rate, loss in errors:
        if rate < 0:
            raise ValueError("an error rate cannot be negative")
        total += rate * effective_drops(loss, mu)
    base = 1.0 - total
    if base < 0.0:
        base = 0.0
    return base * base


def zeroing_rate(log_score_loss_nats, mu):
    """Single-channel error rate ``m* = 1/k`` that zeros a tournament entry."""
    k = effective_drops(log_score_loss_nats, mu)
    if k == 0.0:
        return float("inf")
    return 1.0 / k
