# SPDX-License-Identifier: Apache-2.0
# Part of forecast-answer-formats, by MV2 of Munim, Inc. Made with AI.
#
# Independent reference implementation of the BINARY answer extractor used by a
# third deployed forecasting bot, EskemoMan/metaculus-forecast-bot
# (forecaster/parsing.py :: parse_binary_probability), an open-source hobbyist
# entrant in the Metaculus Fall 2026 FutureEval bot tournament and MiniBench.
#
# IMPORTANT (honesty + licensing): that upstream repository carries NO license
# file. This module copies none of its source. It is an independent
# reimplementation written only from the algorithm's publicly observable,
# documented behaviour, so this benchmark can score it alongside the two
# extractors already covered (mv2-forecaster and Metaculus forecasting-tools).
# Source observed: https://github.com/EskemoMan/metaculus-forecast-bot
#   forecaster/parsing.py (default branch `main`).
#
# Documented behaviour reproduced here:
#   * Normalise: strip markdown emphasis asterisks ("*"), fold a few unicode
#     dashes/spaces/quotes to ASCII. (No lowercasing; matching is case-folded
#     by the regexes instead.)
#   * Scan ONLY the last four non-empty lines, in reverse. On the first line
#     containing the word "probability", require a ":" OR "=" separator within
#     ~30 chars, an optional hedge word, a number, and an OPTIONAL "%"/"percent".
#   * Unit handling: with a unit, divide by 100; without a unit, a value <= 1.0
#     is a raw fraction and a value > 1.0 is divided by 100.
#   * Reject (treated here as a silent DROP -> None) a value outside [0, 1] and a
#     final line that states a range (e.g. "40%-60"); if no line matches, fall
#     back to a stricter whole-text pattern requiring "%", taking the LAST match.
#   * Never injects a default: a failure to parse is a drop, never a guess.

import re

__version__ = "0.1.0"

# Normalisation: strip markdown emphasis asterisks; fold a few unicode glyphs.
_TRANSLATE = {
    ord("*"): None,     # markdown bold / italic / bullets
    0x2013: "-", 0x2014: "-", 0x2212: "-",   # en/em dash, minus -> hyphen
    0x00A0: " ", 0x2009: " ", 0x202F: " ",   # nbsp / thin / narrow spaces
    0x201C: '"', 0x201D: '"', 0x2018: "'", 0x2019: "'",  # curly quotes
}

# "probability" ... (<=30 non-separator chars) ... [: or =] ... optional hedge
# ... number ... optional %/percent unit.
_PROB_LINE = re.compile(
    r"probability[^\n:=]{0,30}[:=]\s*"
    r"(?:~|approx(?:imately)?|about|around)?\s*"
    r"(\d+(?:\.\d+)?)\s*"
    r"(%|percent)?",
    re.IGNORECASE,
)

# Stricter whole-text fallback: "probability" [: or =] number, "%" REQUIRED.
_PROB_STRICT = re.compile(
    r"probability\s*[:=]\s*(\d+(?:\.\d+)?)\s*%",
    re.IGNORECASE,
)

# A range on the final line, e.g. "40%-60" or "3 - 5".
_RANGE = re.compile(r"\d\s*%?\s*-\s*\d")


def normalize(text):
    """Strip markdown emphasis and fold a few unicode glyphs to ASCII."""
    return text.translate(_TRANSLATE)


def _to_prob(value, unit):
    """Convert a raw number + optional unit to a probability in [0, 1]."""
    if unit:
        return value / 100.0
    if value <= 1.0:
        return value
    return value / 100.0


def extract_binary(text):
    """Return the parsed probability in [0, 1], or None when the upstream
    parser would raise ParseError (a silent drop). None is also returned when
    there is no legitimate final forecast, so the caller distinguishes a miss
    from a correct rejection using the ground-truth label, not this function."""
    norm = normalize(text)
    lines = [ln for ln in norm.splitlines() if ln.strip()]
    for line in reversed(lines[-4:]):
        if "probability" not in line.lower():
            continue
        m = _PROB_LINE.search(line)
        if not m:
            continue
        after = re.split(r"[:=]", line, maxsplit=1)[-1]
        if _RANGE.search(after):
            return None  # final line states a range -> ParseError
        prob = _to_prob(float(m.group(1)), m.group(2))
        if prob < 0.0 or prob > 1.0:
            return None  # out of range -> ParseError
        return prob
    # Fallback: stricter whole-text pattern, last match wins.
    matches = list(_PROB_STRICT.finditer(norm))
    if matches:
        prob = float(matches[-1].group(1)) / 100.0
        return prob if 0.0 <= prob <= 1.0 else None
    return None
