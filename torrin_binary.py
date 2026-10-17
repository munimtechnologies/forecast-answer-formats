# SPDX-License-Identifier: Apache-2.0
# Part of forecast-answer-formats, by MV2 of Munim, Inc. Made with AI.
"""Binary-probability extractor of a fifth deployed tournament bot,
Torrin44/forecast-bot (bot/parsing.py, parse_binary).

The regexes, the 300-character fallback window and the reject-out-of-range
logic below follow the upstream function as published; upstream is
Copyright (c) 2026 the forecast-bot authors under the MIT License, whose notice
is reproduced in THIRD_PARTY_NOTICES.md. The packaging, tests and analysis
around it are Apache-2.0.

Behaviour (read from the upstream source, 2026-10-16):
  - primary: every "probability" label followed by ":" or "=", optional
    asterisks before the number, then a number (signs, commas and a leading
    dot allowed) and a literal "%"  (case-insensitive); LAST match wins;
  - fallback, only when the primary finds nothing: the LAST bare "N%" in the
    final 300 characters of the text, label or not;
  - commas are stripped; a value outside [0, 100] is rejected, not clamped;
  - upstream raises ParseError when nothing is found; this benchmark maps
    that to None.

In the deployed bot a ParseError is NOT a dropped run: bot/forecaster.py sends
the last 6,000 characters to a cheap parser model with a repair prompt and
parses its reply again. This benchmark scores the deterministic stage only.
"""

import re

_NUM = r"[-+]?\d[\d,]*(?:\.\d+)?|[-+]?\.\d+"
_PRIMARY = re.compile(rf"probability\s*[:=]\s*\**\s*({_NUM})\s*%", re.IGNORECASE)
_FALLBACK = re.compile(rf"({_NUM})\s*%")
_WINDOW = 300


def torrin_binary(text):
    """Parsed probability in [0, 1], or None (upstream: ParseError -> LLM repair)."""
    if not text:
        return None
    matches = _PRIMARY.findall(text)
    if not matches:
        matches = _FALLBACK.findall(text[-_WINDOW:])
    if not matches:
        return None
    value = float(matches[-1].replace(",", "").replace("−", "-"))
    if not 0 <= value <= 100:
        return None
    return value / 100.0
