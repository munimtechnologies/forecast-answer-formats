# SPDX-License-Identifier: Apache-2.0
# Part of forecast-answer-formats, by MV2 of Munim, Inc. Made with AI.
#
# Self-contained: imports only bowen_binary + the standard library, so the
# publish lane can run it with just these two files present.
# The 20 binary cases are the same corpus as xtool_answer_formats.json. The
# expected classes match the sealed sandbox run bowen-binary-v1 (2026-10-16),
# which scored this extractor against the LIVE corpus with the repo's own
# extractors and first reproduced the published mv2 (14/2/0/4) and
# forecasting-tools (13/3/2/2) tallies as a hard gate.

import unittest

from bowen_binary import bowen_binary

# (id, text, true_prob, expected_class, expected_value)
# expected_value is the probability the extractor should read, or None.
CASES = [
    ("bin_canonical",     "Probability: 73%",            0.73,  "correct",        0.73),
    ("bin_decimal_pct",   "Probability: 73.5%",          0.735, "correct",        0.735),
    ("bin_dropped_pct",   "Probability: 73",             0.73,  "miss",           None),
    ("bin_bare_fraction", "Probability: 0.73",           0.73,  "miss",           None),
    ("bin_no_space",      "Probability:73%",             0.73,  "correct",        0.73),
    ("bin_line_bold",     "**Probability: 73%**",        0.73,  "correct",        0.73),
    ("bin_bold_colon_in", "**Probability:** 73%",        0.73,  "correct",        0.73),
    ("bin_bold_number",   "Probability: **73%**",        0.73,  "correct",        0.73),
    ("bin_italic",        "*Probability:* 73%",          0.73,  "correct",        0.73),
    ("bin_lowercase",     "probability: 73%",            0.73,  "correct",        0.73),
    ("bin_numbered",      "1. Probability: 73%",         0.73,  "correct",        0.73),
    ("bin_boundary_0",    "Probability: 0%",             0.0,   "correct",        0.0),
    ("bin_boundary_100",  "Probability: 100",            1.0,   "miss",           None),
    ("bin_equals",        "Probability = 73%",           0.73,  "correct",        0.73),
    ("bin_prose_is",      "My probability is 73%.",      0.73,  "miss",           None),
    ("bin_baserate_then", "The base rate is 5%.\nProbability: 80%", 0.80, "correct", 0.80),
    ("bin_baserate_only", "Historically about a 5% base rate, nothing else.", None, "correct_reject", None),
    ("bin_two_prose_pcts", "There is a 20% chance of rain and a 30% chance of snow.", None, "correct_reject", None),
    ("bin_out_of_range",  "Probability: 173",            None,  "correct_reject", None),
    ("bin_no_number",     "I am fairly confident it happens.", None, "correct_reject", None),
]


def classify(value, true_prob):
    """Map an extracted value + ground truth to a benchmark class."""
    if true_prob is not None:            # a legitimate final forecast exists
        if value is None:
            return "miss"
        if abs(value - true_prob) < 1e-9:
            return "correct"
        return "wrong_value"
    # no legitimate final forecast
    if value is None:
        return "correct_reject"
    return "false_positive"


class TestBowenBinaryExtractor(unittest.TestCase):

    def test_per_case_value_and_class(self):
        for cid, text, true_prob, exp_class, exp_value in CASES:
            with self.subTest(case=cid):
                value = bowen_binary(text)
                if exp_value is None:
                    self.assertIsNone(value, f"{cid}: expected a drop/reject")
                else:
                    self.assertIsNotNone(value, f"{cid}: expected a read")
                    self.assertAlmostEqual(value, exp_value, places=9,
                                           msg=f"{cid}: wrong value")
                self.assertEqual(classify(value, true_prob), exp_class,
                                 msg=f"{cid}: wrong class")

    def test_published_tally(self):
        tally = {"correct": 0, "miss": 0, "wrong_value": 0,
                 "false_positive": 0, "correct_reject": 0}
        for _cid, text, true_prob, _exp_class, _exp_value in CASES:
            tally[classify(bowen_binary(text), true_prob)] += 1
        # Bowen1314/metaculus-bot's deterministic binary stage on this corpus:
        self.assertEqual(tally["correct"], 12)
        self.assertEqual(tally["miss"], 4)
        self.assertEqual(tally["wrong_value"], 0)
        self.assertEqual(tally["false_positive"], 0)
        self.assertEqual(tally["correct_reject"], 4)
        self.assertEqual(sum(tally.values()), 20)

    def test_zero_false_positives_on_traps(self):
        # Label-gated like mv2 and EskemoMan: reasoning-text %s are never read.
        for text in ("Historically about a 5% base rate, nothing else.",
                     "There is a 20% chance of rain and a 30% chance of snow.",
                     "I am fairly confident it happens."):
            self.assertIsNone(bowen_binary(text))

    def test_percent_required_and_both_separators(self):
        # Reads "=" (mv2 drops it) ...
        self.assertAlmostEqual(bowen_binary("Probability = 73%"), 0.73, places=9)
        # ... but needs a literal "%" (like forecasting-tools), so these drop.
        self.assertIsNone(bowen_binary("Probability: 73"))
        self.assertIsNone(bowen_binary("Probability: 0.73"))
        self.assertIsNone(bowen_binary("Probability: 100"))

    # Probes outside the corpus tally.

    def test_probe_out_of_range_rejected_not_clamped(self):
        self.assertIsNone(bowen_binary("Probability: 150%"))
        self.assertAlmostEqual(bowen_binary("Probability: 100%"), 1.0, places=9)

    def test_probe_last_labeled_match_wins(self):
        text = "Probability: 20%\nOn reflection, revised.\nProbability: 35%"
        self.assertAlmostEqual(bowen_binary(text), 0.35, places=9)

    def test_probe_stale_labeled_draft_beats_unlabeled_final(self):
        # A label-gated last-match reader returns the earlier LABELED draft,
        # not the final answer written in prose.
        text = ("Initial probability: 40%\n"
                "After weighing the evidence I settle on 55%.")
        self.assertAlmostEqual(bowen_binary(text), 0.40, places=9)

    def test_probe_parenthetical_label_dropped(self):
        self.assertIsNone(bowen_binary("Probability (final): 73%"))


if __name__ == "__main__":
    unittest.main()
