"""Self-contained reference transcriptions of two deployed forecasting-bot
binary-answer extractors, so the headline results in this repo are reproducible
offline (no pip install, no network) and can be checked by the test suite.

Each function below is transcribed FROM THE PUBLISHED SOURCE of the tool it
mirrors, with the exact regex quoted. The live tools are also invoked unmodified
by compare_extractors.py (which imports the real packages); these references
exist only so the published tallies are verifiable without that environment.

Sources (read 2026-10-14):
  * mv2_forecaster v0.1.7 parse_binary --
    github.com/munimtechnologies/mv2-forecaster/blob/main/mv2_forecaster.py
    label regex: "Probability" + _PROB_PAD + ":" + _PROB_PAD + "(" + _NUM + ")\\s*(%?)"
    with re.I; _PROB_PAD = r"[\\s*_~`]*"; takes the LAST match; divides by 100
    when a % is present OR the value is > 1; keeps the result only if in [0, 1].
  * Metaculus forecasting-tools PredictionExtractor.extract_last_percentage_value --
    github.com/Metaculus/forecasting-tools/blob/main/forecasting_tools/helpers/prediction_extractor.py
    regex: r"(\\d+(?:\\.\\d+)?)\\s*%"; takes the LAST match; divides by 100; raises
    (-> treated here as a DROP) when no % match is found or the value is outside
    [0, 1] before clamping to [min_prediction, max_prediction] = [0, 1].

Made with AI by MV2 of Munim, Inc. (research field). Apache-2.0.
"""
import re

# --- mv2_forecaster v0.1.7 binary parser (transcribed) ----------------------
_PROB_PAD = r"[\s*_~`]*"
_NUM = r"\d+(?:\.\d+)?"
_MV2_BINARY = re.compile(
    "Probability" + _PROB_PAD + r":" + _PROB_PAD + r"(" + _NUM + r")\s*(%?)",
    re.I,
)


def mv2_binary(text):
    """Return a probability in [0, 1], or None if the answer is dropped."""
    matches = _MV2_BINARY.findall(text)
    if not matches:
        return None
    num_s, pct = matches[-1]
    val = float(num_s)
    if pct == "%" or val > 1.0:
        val = val / 100.0
    return val if 0.0 <= val <= 1.0 else None


# --- Metaculus forecasting-tools binary extractor (transcribed) -------------
_FT_PCT = re.compile(r"(\d+(?:\.\d+)?)\s*%")


def forecasting_tools_binary(text, min_prediction=0.0, max_prediction=1.0):
    """Return a probability in [0, 1], or None if the answer is dropped.

    The real method raises ValueError when no % is found or the value is out of
    [0, 1]; a raise means the run yields no usable forecast, i.e. a DROP, which
    we represent as None.
    """
    matches = _FT_PCT.findall(text)
    if not matches:
        return None  # source raises ValueError("Could not extract prediction ...")
    val = float(matches[-1]) / 100.0
    if val < 0.0 or val > 1.0:
        return None  # source raises before clamping
    return min(max_prediction, max(min_prediction, val))


def classify(got, true_prob):
    """Label an extractor output against ground truth.

    true_prob is None when the text contains no legitimate final forecast, so
    any READ is a FALSE POSITIVE.
    """
    read = got is not None
    if true_prob is None:
        return "false_positive" if read else "correct_reject"
    if not read:
        return "miss"
    return "correct" if abs(got - true_prob) < 1e-6 else "wrong_value"
