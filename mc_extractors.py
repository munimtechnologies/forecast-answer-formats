"""
Reference transcriptions of two deployed forecasting-bot MULTIPLE-CHOICE answer
extractors, for the forecast-answer-formats cross-tool benchmark.

These are faithful, offline reproductions of each tool's PUBLISHED source so the
labeled corpus can be scored deterministically without network or API objects.
They are NOT the upstream packages; the queued live-verification run
(compete: mc-xtool-verify) exercises the real packages unmodified to confirm
these tallies. See xtool_mc.md for the exact source each one mirrors and for the
honest limits of a source-grounded reproduction.

- mv2_mc(): mirrors mv2-forecaster 0.1.7 `parse_multiple_choice`
  (github.com/munimtechnologies/mv2-forecaster). Its MC behaviour is also
  confirmed by real sandbox runs (compete: forecaster-mc-fix-v1,
  forecaster-parser-audit-v1).
- forecasting_tools_mc(): mirrors Metaculus forecasting-tools
  `prediction_extractor._extract_option_probabilities_through_name_matching`
  (github.com/Metaculus/forecasting-tools) -- a SEPARATE project by Metaculus,
  used here only as a transcription for comparison.

License: Apache-2.0. Made with AI, by MV2 of Munim, Inc.
"""
import re

_NUM = r"-?\d[\d,]*(?:\.\d+)?"


def _to_float(s):
    return float(str(s).replace(",", ""))


# --- mv2-forecaster 0.1.7 (faithful transcription) --------------------------
# Verbatim from mv2_forecaster.parse_multiple_choice:
#   _MC_PAD  tolerates whitespace, * _ ~ ` emphasis, '>' quote, '-', and bullet.
#   _MC_LIST optional numbered-list marker like '1.' or '2)'.
#   separator is a REQUIRED literal ':'; '%' is optional; all options required.
_MC_PAD = "[\\s>*_~`\\-•]*"
_MC_LIST = r"(?:\d+[.)]" + _MC_PAD + r")?"


def mv2_mc(text, options):
    probs = {}
    for opt in options:
        pat = (r"^" + _MC_PAD + _MC_LIST + re.escape(str(opt))
               + _MC_PAD + r":" + _MC_PAD + r"(" + _NUM + r")\s*%?")
        hits = re.findall(pat, text, re.I | re.M)
        if not hits:
            return None
        probs[opt] = max(_to_float(hits[-1]), 0.0)
    total = sum(probs.values())
    if total <= 0:
        return None
    return {k: v / total for k, v in probs.items()}


# --- Metaculus forecasting-tools (faithful transcription) -------------------
# Verbatim behaviour of the per-option regex, searched per line against each
# cleaned (stripped+lowercased) line:
#   ^\s*\W* {name} (?![\w.,-]) \s*\W* [|:] \s* (number)
# Delimiter is ':' OR table-pipe '|'; NO \W* sits between the delimiter and the
# number. Exactly one matching line is required per option, else the whole run
# is dropped. Upstream additionally tries alias name-lists ("Option {i}" etc.);
# that path is irrelevant here because the corpus uses the canonical option
# names verbatim, so literal matching reproduces its success path exactly.
def _clean(s):
    return s.strip().lower()


def forecasting_tools_mc(text, options):
    cleaned_lines = [_clean(ln) for ln in text.split("\n")]
    values = []
    for opt in options:
        name = re.escape(_clean(str(opt)))
        pat = re.compile(
            r"^\s*\W*" + name + r"(?![\w.,-])\s*\W*[|:]\s*(" + _NUM + r")",
            re.I,
        )
        matches = [m.group(1) for ln in cleaned_lines
                   for m in [pat.search(ln)] if m]
        if len(matches) != 1:
            return None
        values.append(_to_float(matches[0]))
    # Upstream infers decimal vs percentage, clamps >=0, renormalises to sum 1.
    if any(v > 1.0 for v in values):
        values = [v / 100.0 for v in values]
    values = [max(v, 0.0) for v in values]
    total = sum(values)
    if total <= 0:
        return None
    return {opt: v / total for opt, v in zip(options, values)}
