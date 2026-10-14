"""Cross-tool answer-format robustness map for forecasting-bot extractors.

This runs ONE labeled corpus of realistic LLM structured-answer strings through
TWO independent, deployed extractors and records, per case, which READS the answer
and which silently DROPs it (returns None / raises -> that run is excluded from
the ensemble, biasing the aggregate or skipping the question):

  * mv2_forecaster (live main, github.com/munimtechnologies/mv2-forecaster),
    parse_binary / parse_multiple_choice / parse_percentiles.
  * Metaculus's official `forecasting-tools` package (pip), the
    PredictionExtractor used by the Q-template bots in that framework.

Why this is novel and worth publishing: forecasting/eval harnesses extract a
bot's answer from free-form model text with brittle regexes, and a valid answer
in an unexpected shape (a dropped %, a bare fraction, prose, a base rate) is
silently lost or, worse, a reasoning-text number is mistaken for the forecast.
Each extractor embeds its own private regex; there is NO public, standardized
corpus comparing which valid formats different real extractors read vs. drop, or
measuring their false-positive behaviour on reasoning text. This produces one.

The headline, execution-grounded comparison is on BINARY (the most common
Metaculus question type) because the two tools' binary APIs are directly
comparable (both yield a probability in [0,1]). Each binary case carries a
ground truth -- `true_prob` (the probability a careful reader should extract) or
None if the text contains NO legitimate final forecast, so any READ is a FALSE
POSITIVE. Multiple-choice and numeric-percentile cases are characterized against
the live mv2 parsers only (the forecasting-tools MC/numeric APIs need a question
object; that cross-tool comparison is future work).

Run after `python fetch_live.py` (which places mv2_forecaster.py alongside this
file). Outputs xtool_answer_formats.json + xtool_robustness.md to --out-dir.

Made with AI by MV2 of Munim, Inc. (research field). Apache-2.0.
"""
import argparse
import json
import os

import mv2_forecaster as mf

MV2_VERSION = getattr(mf, "__version__", "?")

# --- Load the official Metaculus forecasting-tools extractor, if installed. ----
FT_VERSION = None
FT_ERR = None
_ft_extract = None
try:
    try:
        from forecasting_tools import PredictionExtractor  # type: ignore
    except Exception:
        from forecasting_tools.helpers.prediction_extractor import (  # type: ignore
            PredictionExtractor,
        )
    try:
        from importlib.metadata import version as _ver
        FT_VERSION = _ver("forecasting-tools")
    except Exception:
        FT_VERSION = "installed(unknown version)"

    def _ft_extract(text):
        # Returns a probability in [0,1] or None (DROP). The Q-template bots call
        # this exactly as below for binary questions.
        return PredictionExtractor.extract_last_percentage_value(
            text, max_prediction=1, min_prediction=0)
except Exception as e:  # pragma: no cover - import environment dependent
    FT_ERR = f"{type(e).__name__}: {e}"


def ft_binary(text):
    """(read, value, note) for the official extractor on a binary answer."""
    if _ft_extract is None:
        return None, None, "unavailable"
    try:
        got = _ft_extract(text)
    except Exception as e:
        return False, None, f"drop:{type(e).__name__}"
    if got is None:
        return False, None, "drop:None"
    try:
        got = float(got)
    except Exception:
        return False, None, "drop:non-numeric"
    return True, got, ""


def classify(got, true_prob):
    """Label an extractor result against ground truth."""
    read = got is not None
    if true_prob is None:
        return ("false_positive" if read else "correct_reject")
    if not read:
        return "miss"
    return ("correct" if abs(got - true_prob) < 1e-6 else "wrong_value")


# (id, family, text, true_prob or None) -- None => no legitimate forecast present.
BINARY = [
    ("bin_canonical",       "canonical",            "Probability: 73%",            0.73),
    ("bin_decimal_pct",     "decimal percent",      "Probability: 73.5%",          0.735),
    ("bin_dropped_pct",     "dropped % sign",       "Probability: 73",             0.73),
    ("bin_bare_fraction",   "bare fraction",        "Probability: 0.73",           0.73),
    ("bin_no_space",        "no space",             "Probability:73%",             0.73),
    ("bin_line_bold",       "whole line bold",      "**Probability: 73%**",        0.73),
    ("bin_bold_colon_in",   "bold, colon inside",   "**Probability:** 73%",        0.73),
    ("bin_bold_number",     "number bolded",        "Probability: **73%**",        0.73),
    ("bin_italic",          "italic",               "*Probability:* 73%",          0.73),
    ("bin_lowercase",       "lowercase",            "probability: 73%",            0.73),
    ("bin_numbered",        "numbered line",        "1. Probability: 73%",         0.73),
    ("bin_boundary_0",      "boundary 0%",          "Probability: 0%",             0.0),
    ("bin_boundary_100",    "boundary 100",         "Probability: 100",            1.0),
    ("bin_equals",          "equals separator",     "Probability = 73%",           0.73),
    ("bin_prose_is",        "prose 'is'",           "My probability is 73%.",      0.73),
    ("bin_baserate_then",   "base rate then final", "The base rate is 5%.\nProbability: 80%", 0.80),
    ("bin_baserate_only",   "base rate only (trap)","Historically about a 5% base rate, nothing else.", None),
    ("bin_two_prose_pcts",  "two prose %s (trap)",  "There is a 20% chance of rain and a 30% chance of snow.", None),
    ("bin_out_of_range",    "out of range",         "Probability: 173",            None),
    ("bin_no_number",       "no number at all",     "I am fairly confident it happens.", None),
]

OPTS = ["Option A", "Option B"]
MC = [
    ("mc_canonical",      "canonical",          "Option A: 30%\nOption B: 70%", True),
    ("mc_numbered_dot",   "numbered '1.'",      "1. Option A: 30%\n2. Option B: 70%", True),
    ("mc_bold_colon_in",  "bold, colon inside", "**Option A:** 30%\n**Option B:** 70%", True),
    ("mc_dash_bullet",    "dash bullet",        "- Option A: 30%\n- Option B: 70%", True),
    ("mc_no_percent",     "no percent sign",    "Option A: 30\nOption B: 70", True),
    ("mc_equals",         "equals separator",   "Option A = 30%\nOption B = 70%", False),
    ("mc_parenthetical",  "parenthetical",      "Option A (30%)\nOption B (70%)", False),
]

PCT = [
    ("pct_canonical",   "canonical 'Percentile P:'", "Percentile 10: 100\nPercentile 50: 200\nPercentile 90: 400", True),
    ("pct_dollar",      "dollar + commas",           "Percentile 10: $1,200\nPercentile 50: $3,500\nPercentile 90: $9,000", True),
    ("pct_bold",        "bold line",                 "**Percentile 10:** 100\n**Percentile 50:** 200\n**Percentile 90:** 400", True),
    ("pct_ordinal",     "'10th percentile:' order",  "10th percentile: 100\n50th percentile: 200\n90th percentile: 400", None),
    ("pct_too_few",     "too few (<3)",              "Percentile 50: 200", False),
    ("pct_prose",       "prose, no labels",          "The median is about 200.", False),
]


def run():
    cases = []
    print(f"=== cross-tool answer-format robustness map ===")
    print(f"mv2_forecaster __version__ = {MV2_VERSION}")
    print(f"forecasting-tools version  = {FT_VERSION}  (import error: {FT_ERR})\n")

    print("-- BINARY: mv2.parse_binary  vs  forecasting-tools PredictionExtractor --")
    tally = {"mv2": {}, "ft": {}}
    for cid, fam, text, true_prob in BINARY:
        mv2_got = mf.parse_binary(text)
        ft_read, ft_got, ft_note = ft_binary(text)
        mv2_cls = classify(mv2_got, true_prob)
        ft_cls = classify(ft_got, true_prob) if ft_note != "unavailable" else "unavailable"
        tally["mv2"][mv2_cls] = tally["mv2"].get(mv2_cls, 0) + 1
        tally["ft"][ft_cls] = tally["ft"].get(ft_cls, 0) + 1
        ms = f"{mv2_got:.3f}" if isinstance(mv2_got, float) else "None"
        fs = f"{ft_got:.3f}" if isinstance(ft_got, float) else "None"
        print(f"  {fam:24s} true={str(true_prob):5s} | mv2 {ms:>6}={mv2_cls:14s}"
              f" | ft {fs:>6}={ft_cls}")
        cases.append({"id": cid, "type": "binary", "family": fam, "text": text,
                      "true_prob": true_prob,
                      "mv2_read": mv2_got is not None, "mv2_value": mv2_got,
                      "mv2_class": mv2_cls,
                      "ft_read": bool(ft_read), "ft_value": ft_got,
                      "ft_note": ft_note, "ft_class": ft_cls})
    print(f"  mv2 tally: {tally['mv2']}")
    print(f"  ft  tally: {tally['ft']}\n")

    print("-- MULTIPLE CHOICE: mv2.parse_multiple_choice (mv2-only) --")
    for cid, fam, text, should_read in MC:
        got = mf.parse_multiple_choice(text, OPTS)
        read = got is not None
        ok = read == should_read
        print(f"  [{'READ' if read else 'DROP'}] {fam:22s} expect={'READ' if should_read else 'DROP'}"
              + ("" if ok else "  UNEXPECTED"))
        cases.append({"id": cid, "type": "multiple_choice", "family": fam, "text": text,
                      "options": OPTS, "intended_readable": should_read,
                      "mv2_read": read, "mv2_value": got, "mv2_ok": ok})

    print("\n-- NUMERIC PERCENTILES: mv2.parse_percentiles (mv2-only) --")
    for cid, fam, text, should_read in PCT:
        got = mf.parse_percentiles(text)
        read = got is not None
        ok = None if should_read is None else (read == should_read)
        shown = (", ".join(f"{k}:{v:g}" for k, v in sorted(got.items()))) if read else "None"
        flag = "" if ok in (True, None) else "  UNEXPECTED"
        print(f"  [{'READ' if read else 'DROP'}] {fam:26s} -> {shown}{flag}")
        cases.append({"id": cid, "type": "numeric_percentiles", "family": fam, "text": text,
                      "intended_readable": should_read, "mv2_read": read,
                      "mv2_value": got, "mv2_ok": ok})

    dataset = {
        "name": "forecast-answer-formats-xtool",
        "description": "A labeled corpus of realistic LLM structured-answer "
                       "formats for forecasting bots, run through two deployed "
                       "extractors (mv2-forecaster and Metaculus forecasting-tools) "
                       "to map which valid formats each reads vs. silently drops, "
                       "and each extractor's false-positive behaviour on reasoning "
                       "text. First-of-its-kind cross-tool robustness benchmark.",
        "generated_by": "mv2-forecaster compare_extractors.py, made with AI by MV2 of Munim, Inc.",
        "mv2_version": MV2_VERSION,
        "forecasting_tools_version": FT_VERSION,
        "forecasting_tools_import_error": FT_ERR,
        "license": "CC BY 4.0",
        "binary_tally": tally,
        "cases": cases,
    }
    return dataset


def write_outputs(dataset, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    jp = os.path.join(out_dir, "xtool_answer_formats.json")
    with open(jp, "w", encoding="utf-8") as fh:
        json.dump(dataset, fh, indent=2)
    print(f"\nwrote {jp}")

    L = ["# Cross-tool forecast answer-format robustness map", "",
         f"Extractors: **mv2_forecaster {dataset['mv2_version']}** vs. "
         f"**Metaculus forecasting-tools {dataset['forecasting_tools_version']}**.",
         "",
         "A DROP returns None (the run is excluded from the ensemble). A FALSE "
         "POSITIVE reads a probability from text that contains no legitimate final "
         "forecast (e.g. a base rate or a prose percentage) -- worse than a drop, "
         "since it injects a spurious forecast.",
         "", "## Binary", "",
         "| family | true | mv2 | mv2 class | forecasting-tools | ft class |",
         "|---|---|---|---|---|---|"]
    for c in dataset["cases"]:
        if c["type"] != "binary":
            continue
        ms = f"{c['mv2_value']:.3f}" if isinstance(c["mv2_value"], float) else "DROP"
        fs = f"{c['ft_value']:.3f}" if isinstance(c["ft_value"], float) else "DROP"
        L.append(f"| {c['family']} | {c['true_prob']} | {ms} | {c['mv2_class']} "
                 f"| {fs} | {c['ft_class']} |")
    L += ["", f"Binary tally -- mv2: `{dataset['binary_tally']['mv2']}`; "
          f"forecasting-tools: `{dataset['binary_tally']['ft']}`.", ""]
    L += ["## Multiple choice (mv2-only)", "",
          "| family | read? | expected |", "|---|---|---|"]
    for c in dataset["cases"]:
        if c["type"] != "multiple_choice":
            continue
        L.append(f"| {c['family']} | {'READ' if c['mv2_read'] else 'DROP'} "
                 f"| {'READ' if c['intended_readable'] else 'DROP'} |")
    L += ["", "## Numeric percentiles (mv2-only)", "",
          "| family | read? |", "|---|---|"]
    for c in dataset["cases"]:
        if c["type"] != "numeric_percentiles":
            continue
        L.append(f"| {c['family']} | {'READ' if c['mv2_read'] else 'DROP'} |")
    L += ["", "Made with AI by MV2 of Munim, Inc. Data: CC BY 4.0. "
          "forecasting-tools is a separate project by Metaculus; it is invoked "
          "here unmodified via pip for comparison."]
    mp = os.path.join(out_dir, "xtool_robustness.md")
    with open(mp, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")
    print(f"wrote {mp}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default=os.environ.get("OUT_DIR", "."))
    args = ap.parse_args()
    out_dir = args.out_dir if os.path.isdir(os.path.dirname(args.out_dir) or ".") else "out"
    data = run()
    write_outputs(data, out_dir)
    print("\nDONE. forecasting-tools available:", _ft_extract is not None)
