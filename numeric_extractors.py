# numeric_extractors.py
# Source-grounded reference transcriptions of two deployed forecasting-bot
# percentile (numeric) extractors, so the labeled corpus can be checked offline
# in CI. The live packages are exercised unmodified by compare_extractors.py
# (which needs network + installs). These are reimplementations, not imports.
#
# Apache-2.0. Made with AI by MV2 of Munim, Inc.
#
# mv2-forecaster parse_percentiles (v0.1.7), transcribed from the published
#   source at github.com/munimtechnologies/mv2-forecaster:
#     _PROB_PAD = r"[\s*_~`]*"
#     _NUM      = r"-?\d[\d,]*(?:\.\d+)?(?:[eE][-+]?\d+)?|-?\.\d+"
#     pattern   = "Percentile" + PAD + r"(\d+)" + PAD + r":" + PAD
#                 + r"\$?(" + _NUM + r")"        (compiled with re.I)
#   Keeps indices strictly between 0 and 100; returns the {index: value} map
#   only if >= 3 valid percentiles are found, else None.
#
# forecasting-tools (Metaculus) numeric extraction, transcribed from
#   forecasting_tools/helpers/prediction_extractor.py:
#     line filter  r"^\s*(?:(?:[Pp]ercentile\s+\d+)|\d+\s*(?:th|st|nd|rd)?"
#                  r"\s*[Pp]ercentile)\s*[:\-\s]\s*\S+.*"
#     number parse r"(-)?\s*(?:[^\w\s,.-]*\s*)?(\d+(?:,\d{3})*(?:\.\d+)?)"
#   First number on a line is the percentile level, second is the value; the
#   level is divided by 100. Downstream distribution-count validation lives in
#   the library, not in the text extractor, so it is not modeled here.

import re

_PROB_PAD = r"[\s*_~`]*"
_MV2_NUM = r"-?\d[\d,]*(?:\.\d+)?(?:[eE][-+]?\d+)?|-?\.\d+"
_MV2_PERC = re.compile(
    "Percentile" + _PROB_PAD + r"(\d+)" + _PROB_PAD + r":" + _PROB_PAD
    + r"\$?(" + _MV2_NUM + r")",
    re.I,
)

_FT_PERC_LINE = re.compile(
    r"^\s*(?:(?:[Pp]ercentile\s+\d+)|\d+\s*(?:th|st|nd|rd)?\s*[Pp]ercentile)"
    r"\s*[:\-\s]\s*\S+.*",
    re.M,
)
_FT_NUM = re.compile(r"(-)?\s*(?:[^\w\s,.-]*\s*)?(\d+(?:,\d{3})*(?:\.\d+)?)")


def _to_float(s):
    return float(s.replace(",", ""))


def mv2_percentiles(text):
    """Return {percentile_index: value} or None if the block is dropped."""
    found = {}
    for idx_s, val_s in _MV2_PERC.findall(text):
        idx = int(idx_s)
        if not (0 < idx < 100):
            continue
        found[idx] = _to_float(val_s)
    return found if len(found) >= 3 else None


def forecasting_tools_percentiles(text):
    """Return [(level_fraction, value), ...] or None if nothing is read.

    Each line that passes the percentile line filter contributes
    (first_number / 100, second_number). A line with fewer than two numbers is
    skipped. An empty result is a DROP (None), matching the library convention
    of mapping a failed extraction to no prediction.
    """
    pairs = []
    for line in _FT_PERC_LINE.findall(text):
        nums = []
        for sign, digits in _FT_NUM.findall(line):
            v = _to_float(digits)
            if sign == "-":
                v = -v
            nums.append(v)
        if len(nums) >= 2:
            pairs.append((nums[0] / 100.0, nums[1]))
    return pairs or None


def ft_as_percentile_map(pairs):
    """Convert forecasting-tools output to {int percentile: value} or None."""
    if pairs is None:
        return None
    return {int(round(level * 100)): value for level, value in pairs}


def _maps_equal(a, b, tol=1e-6):
    if a is None or b is None:
        return a is b
    if set(a) != set(b):
        return False
    return all(abs(a[k] - b[k]) <= tol for k in a)


def classify_percentiles(got_map, intended_map):
    """Label an extracted percentile map against ground truth.

    got_map / intended_map are {int index: value} or None. An intended_map of
    None means there was no valid final answer (a trap case): a read there is a
    false positive, no read is a correct reject.
    """
    read = got_map is not None
    if intended_map is None:
        return "false_positive" if read else "correct_reject"
    if not read:
        return "miss"
    return "correct" if _maps_equal(got_map, intended_map) else "wrong_value"
