# SPDX-License-Identifier: Apache-2.0
# Part of forecast-answer-formats, by MV2 of Munim, Inc. Made with AI.
#
# Independent reference implementation of the NUMERIC (percentile) answer
# extractor used by a third deployed forecasting bot,
# EskemoMan/metaculus-forecast-bot (forecaster/parsing.py :: parse_percentiles),
# an open-source hobbyist entrant in the Metaculus Fall 2026 FutureEval bot
# tournament and MiniBench. The binary leg of this tool was added in v0.9.0
# (eskemo_extractor.py); this module adds the numeric leg so the numeric corpus
# (xtool_numeric_formats.json) is scored three-way, as the binary corpus already
# is.
#
# IMPORTANT (honesty + licensing): the upstream repository carries NO license
# file. This module copies none of its source. It is an independent
# reimplementation written only from the algorithm's publicly observable,
# documented behaviour, so this benchmark can score it alongside the two
# extractors already covered (mv2-forecaster and Metaculus forecasting-tools).
# Source observed: https://github.com/EskemoMan/metaculus-forecast-bot
#   forecaster/parsing.py (default branch `main`).
#
# Documented behaviour reproduced here:
#   * Normalise: strip markdown emphasis asterisks ("*"), fold a few unicode
#     dashes/spaces/quotes to ASCII (the same normaliser as the binary path).
#   * Scan EVERY non-empty line (no last-N window, unlike the binary path). On
#     each line, try four patterns in order; the first that matches wins:
#       1. "Percentile <level>: <value>"
#       2. "<level>th percentile: <value>"
#       3. "P<level>: <value>"
#       4. a table row "| <level> | <value>"
#     Separators allowed between level and value are ':', '=' or '|'.
#   * Level token: a 1-2 digit integer with an optional ordinal suffix
#     (st/nd/rd/th), which is discarded. Value token: an optional currency
#     prefix ($/EUR/GBP/...), comma-grouped or plain digits, optional decimal
#     and exponent, and an optional scale suffix (k/M/B/T/thousand/million/...).
#     There is NO '%' handling in the percentile path.
#   * The last occurrence of each level wins. The caller supplies the EXPECTED
#     list of percentile levels the question declares; parsing raises ParseError
#     (modelled here as a silent DROP) if any expected level is missing, or if
#     the read values decrease across the ordered levels.
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

# A percentile level: 1-2 digits, optional decimal, optional discarded ordinal.
_LEVEL = r"(\d{1,2}(?:\.\d+)?)(?:st|nd|rd|th)?"

# A numeric value: optional sign; comma-grouped or plain digits; optional
# decimal; optional exponent; or a bare ".\d+" form.
_NUM = (r"[-+]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?(?:[eE][-+]?\d+)?"
        r"|[-+]?\.\d+")

# Optional currency prefix in front of a value.
_CUR = r"(?:[$€£¥]|usd|eur|gbp)?\s*"

# Optional scale suffix after a value (captured so it can be applied).
_SUF = r"(?:\s*(thousand|million|billion|trillion|bn|mn|[kKMBT]))?"

# The whole value token: currency, the number (captured), an optional scale.
_VALUE = _CUR + r"(" + _NUM + r")" + _SUF

# Four line patterns; group(1)=level, group(2)=number, group(3)=scale suffix.
_P1 = re.compile(r"percentile\s*" + _LEVEL + r"\s*[:=|]\s*" + _VALUE, re.I)
_P2 = re.compile(_LEVEL + r"\s*percentile\s*[:=|]\s*" + _VALUE, re.I)
_P3 = re.compile(r"\bp\s*" + _LEVEL + r"\s*[:=|]\s*" + _VALUE, re.I)
_P4 = re.compile(r"^\s*\|?\s*(?:percentile\s*)?" + _LEVEL
                 + r"\s*(?:percentile)?\s*\|\s*" + _VALUE, re.I)
_PATTERNS = (_P1, _P2, _P3, _P4)

_SCALES = {
    "thousand": 1e3, "k": 1e3,
    "million": 1e6, "mn": 1e6, "m": 1e6,
    "billion": 1e9, "bn": 1e9, "b": 1e9,
    "trillion": 1e12, "t": 1e12,
}


class ParseError(Exception):
    """Raised when the upstream parser would reject the block (a silent drop)."""


def normalize(text):
    """Strip markdown emphasis and fold a few unicode glyphs to ASCII."""
    return text.translate(_TRANSLATE)


def _to_float(s):
    v = float(s.replace(",", ""))
    if v != v or v in (float("inf"), float("-inf")):
        raise ParseError("non-finite number")
    return v


def _apply_scale(value, suffix):
    if not suffix:
        return value
    scale = _SCALES.get(suffix.lower())
    return value * scale if scale else value


def parse_percentiles(text, expected):
    """Return sorted [(level_in_0_1, value), ...] for the EXPECTED levels, or
    raise ParseError (a silent drop) if any expected level is missing or the
    values decrease. `expected` is the list of percentile levels the question
    declares (floats or ints), not a count."""
    norm = normalize(text)
    found = {}
    for line in norm.splitlines():
        if not line.strip():
            continue
        for pat in _PATTERNS:
            m = pat.search(line)
            if not m:
                continue
            level = float(m.group(1))
            value = _apply_scale(_to_float(m.group(2)), m.group(3))
            found[level] = value       # last occurrence of a level wins
            break
    missing = [p for p in expected if float(p) not in found]
    if missing:
        raise ParseError("missing %d percentile level(s)" % len(missing))
    ordered = [(float(p) / 100.0, found[float(p)]) for p in sorted(expected)]
    values = [v for _, v in ordered]
    for i in range(len(values) - 1):
        if values[i] > values[i + 1]:
            raise ParseError("percentile values decrease")
    return ordered


def extract_numeric(text, expected_levels):
    """Return {int level: value} the extractor would read, or None on a drop.

    `expected_levels` is the list of percentile levels the question declares.
    None is also returned when there is no legitimate final answer, so the
    caller distinguishes a miss from a correct rejection using the ground-truth
    label, not this function."""
    try:
        pairs = parse_percentiles(text, expected_levels)
    except ParseError:
        return None
    return {int(round(p * 100)): v for p, v in pairs}


def _maps_equal(a, b, tol=1e-6):
    if a is None or b is None:
        return a is b
    if set(a) != set(b):
        return False
    return all(abs(a[k] - b[k]) <= tol for k in a)


def classify_numeric(got_map, intended_map):
    """Label an extracted percentile map against ground truth.

    got_map / intended_map are {int level: value} or None. An intended_map of
    None means there was no valid final answer (a trap case): a read there is a
    false positive, no read is a correct reject."""
    read = got_map is not None
    if intended_map is None:
        return "false_positive" if read else "correct_reject"
    if not read:
        return "miss"
    return "correct" if _maps_equal(got_map, intended_map) else "wrong_value"
