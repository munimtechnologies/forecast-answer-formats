# SPDX-License-Identifier: Apache-2.0
# Part of forecast-answer-formats, by MV2 of Munim, Inc. Made with AI.
#
# Independent reference implementation of the MULTIPLE-CHOICE answer extractor
# used by a third deployed forecasting bot,
# EskemoMan/metaculus-forecast-bot (forecaster/parsing.py ::
# parse_multiple_choice), an open-source hobbyist entrant in the Metaculus Fall
# 2026 FutureEval bot tournament and MiniBench. The binary leg of this tool was
# added in v0.9.0 (eskemo_extractor.py) and the numeric leg in v0.10.0
# (eskemo_numeric.py); this module adds the multiple-choice leg, so all three
# corpora are now scored three-way.
#
# IMPORTANT (honesty + licensing): the upstream repository carries NO license
# file. This module copies none of its source. It is an independent
# reimplementation written only from the algorithm's publicly observable,
# documented behaviour, so this benchmark can score it alongside the two
# extractors already covered (mv2-forecaster and Metaculus forecasting-tools).
# Source observed: https://github.com/EskemoMan/metaculus-forecast-bot
#   forecaster/parsing.py (default branch `main`), read 2026-10-16.
#
# Documented behaviour reproduced here:
#   * Normalise the whole text once: strip markdown emphasis asterisks ("*"),
#     fold a few unicode dashes/spaces/quotes to ASCII (same normaliser as the
#     binary and numeric paths).
#   * Option keys: each option label normalised, casefolded, whitespace
#     collapsed, quotes/backticks and trailing periods stripped. Two options that
#     collide after this are an error.
#   * Each stripped line is parsed one of two ways:
#       - a TABLE ROW only if it STARTS with '|': split on '|', drop empty cells,
#         label = first cell, value = last cell, which must be exactly a number
#         with an optional '%' / 'percent';
#       - otherwise: drop one leading bullet ('-', bullet glyph or '>') or a
#         numbered marker ('1.' / '1)'), strip quotes, then require
#         "<label> ':' or '=' <number> [%|percent] [(note)] [.]" to the end of
#         the line.
#     The label (and the label with a leading "Option" word removed) must equal
#     an option key exactly.
#   * Hits group into blocks: a hit joins the current block if it is at most
#     two lines after the previous hit (one non-matching line may sit between).
#   * Blocks are tried from LAST to FIRST; the first block that names every
#     option is used (a later line for the same option overwrites an earlier
#     one). There is no last-N-lines window and no reasoning-text guard.
#   * Scale: values are fractions only if no '%' appears AND every value is
#     <= 1; otherwise they are percentages. Negative values, or a total outside
#     [0.9, 1.1], raise; otherwise each value is renormalised by the total.
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

# A numeric value: optional sign; comma-grouped or plain digits; optional
# decimal; optional exponent; or a bare ".\d+" form.
_NUM = (r"[-+]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?(?:[eE][-+]?\d+)?"
        r"|[-+]?\.\d+")

# A non-table line: label, ':' or '=', number, optional percent, optional
# parenthetical note, optional full stop, end of line.
_LINE = re.compile(r"^(.*?)\s*[:=]\s*(" + _NUM + r")\s*(%|percent)?"
                   r"\s*(?:\([^()]*\))?\s*\.?$", re.I)

# The value cell of a table row: exactly a number with an optional percent.
_CELL = re.compile(r"(" + _NUM + r")\s*(%|percent)?", re.I)

_BULLET = re.compile("^(?:[-•>]\\s+)")
_NUMBERED = re.compile(r"^\d{1,2}[.)]\s+")
_OPTION_WORD = re.compile(r"^option\s*[:\-]?\s*", re.I)


class ParseError(Exception):
    """Raised when the upstream parser would reject the text (a silent drop)."""


def normalize(text):
    """Strip markdown emphasis and fold a few unicode glyphs to ASCII."""
    return text.translate(_TRANSLATE)


def _key(label):
    """Comparable form of an option label."""
    k = re.sub(r"\s+", " ", normalize(label).casefold()).strip()
    return k.strip("\"'`").strip().rstrip(".").strip()


def _to_float(s):
    v = float(s.replace(",", ""))
    if v != v or v in (float("inf"), float("-inf")):
        raise ParseError("non-finite number")
    return v


def _undecorate(line):
    line = _BULLET.sub("", line.strip())
    line = _NUMBERED.sub("", line)
    return line.strip().strip("\"'`").strip()


def _match_option(label, keys):
    for cand in (label, _OPTION_WORD.sub("", label)):
        k = _key(cand)
        if k in keys:
            return keys[k]
    return None


def _parse_line(line, keys):
    """Return (option, value, has_percent) for one line, or None."""
    stripped = line.strip()
    if stripped.startswith("|"):
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        cells = [c for c in cells if c]
        if len(cells) < 2:
            return None
        m = _CELL.fullmatch(cells[-1])
        if not m:
            return None
        label, number, pct = cells[0], m.group(1), m.group(2)
    else:
        m = _LINE.match(_undecorate(stripped))
        if not m:
            return None
        label, number, pct = m.group(1), m.group(2), m.group(3)
    option = _match_option(label, keys)
    if option is None:
        return None
    return option, _to_float(number), bool(pct)


def parse_multiple_choice(text, options):
    """Return {option: probability} or raise ParseError (a silent drop)."""
    keys = {_key(o): o for o in options}
    if len(keys) != len(options):
        raise ParseError("options are not distinguishable after normalisation")
    hits = []
    for i, line in enumerate(normalize(text).splitlines()):
        if line.strip():
            hit = _parse_line(line, keys)
            if hit is not None:
                hits.append((i, hit))
    if not hits:
        raise ParseError("no option probabilities found")
    blocks = []
    for i, hit in hits:
        if blocks and i - blocks[-1][-1][0] <= 2:
            blocks[-1].append((i, hit))
        else:
            blocks.append([(i, hit)])
    for block in reversed(blocks):
        values = {}
        for _i, (option, value, pct) in block:
            values[option] = (value, pct)    # later line for an option wins
        if set(values) != set(options):
            continue
        any_pct = any(pct for _v, pct in values.values())
        all_small = all(v <= 1.0 for v, _pct in values.values())
        scale = 1.0 if (not any_pct and all_small) else 100.0
        probs = {o: v / scale for o, (v, _pct) in values.items()}
        if any(p < 0 for p in probs.values()):
            raise ParseError("negative option probability")
        total = sum(probs.values())
        if not 0.9 <= total <= 1.1:
            raise ParseError("option probabilities do not sum to ~100%")
        return {o: p / total for o, p in probs.items()}
    raise ParseError("no block lists every option")


def extract_mc(text, options):
    """Return {option: probability} the extractor would read, or None on a drop.

    None is also returned when there is no legitimate final answer, so the
    caller distinguishes a miss from a correct rejection using the ground-truth
    label, not this function."""
    try:
        return parse_multiple_choice(text, options)
    except ParseError:
        return None
