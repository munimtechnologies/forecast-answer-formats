# SPDX-License-Identifier: Apache-2.0
# Part of forecast-answer-formats, by MV2 of Munim, Inc. Made with AI.
"""Binary-probability extractor of a fourth deployed tournament bot,
Bowen1314/metaculus-bot (bot/parsing.py, parse_binary_probability).

The regex and the last-match / reject-out-of-range logic below follow the
upstream function as published; upstream is Copyright (c) 2026 Bowen Rui under
the MIT License, whose notice is reproduced in THIRD_PARTY_NOTICES.md. The
packaging, tests and analysis around it are Apache-2.0.

Behaviour (checked against the upstream source, 2026-10-16):
  - find every "probability" label followed by ":" or "=" (markdown asterisks
    and whitespace allowed around the separator), then 1-3 digits with an
    optional decimal part, then a literal "%"  (case-insensitive);
  - take the LAST such match;
  - return value/100 when 0 <= value <= 100, else None (rejects, never clamps);
  - return None when nothing matches.

In the deployed bot a None is NOT a dropped run: bot/forecaster.py then hands
the reasoning to the forecasting-tools LLM parser (structure_output). This
benchmark scores the deterministic stage only, so a "miss" or "correct_reject"
here means "deferred to the LLM parser". See xtool_four_way.md.
"""

import math
import re

# label ("probability") + optional ** + [:=] + optional ** + number + "%"
_PROBABILITY = re.compile(
    r"probability\s*\**\s*[:=]\s*\**\s*(?P<num>\d{1,3}(?:\.\d+)?)\s*%",
    re.IGNORECASE,
)


def bowen_binary(text):
    """Parsed probability in [0, 1], or None (upstream: defer to the LLM parser)."""
    if not text:
        return None
    matches = list(_PROBABILITY.finditer(text))
    if not matches:
        return None
    value = float(matches[-1].group("num"))
    if not (0.0 <= value <= 100.0) or math.isnan(value):
        return None
    return value / 100.0
