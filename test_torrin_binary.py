# SPDX-License-Identifier: Apache-2.0
# Part of forecast-answer-formats, by MV2 of Munim, Inc. Made with AI.
#
# Self-contained: imports only torrin_binary + the standard library, so the
# publish lane can run it with just these two files present.
# The 20 binary cases are the same corpus as xtool_answer_formats.json; the
# expected classes are hand-traced from the upstream source.

import unittest

from torrin_binary import torrin_binary

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
    ("bin_prose_is",      "My probability is 73%.",      0.73,  "correct",        0.73),
    ("bin_baserate_then", "The base rate is 5%.\nProbability: 80%", 0.80, "correct", 0.80),
    ("bin_baserate_only", "Historically about a 5% base rate, nothing else.", None, "false_positive", 0.05),
    ("bin_two_prose_pcts", "There is a 20% chance of rain and a 30% chance of snow.", None, "false_positive", 0.30),
    ("bin_out_of_range",  "Probability: 173",            None,  "correct_reject", None),
    ("bin_no_number",     "I am fairly confident it happens.", None, "correct_reject", None),
]

# Filler with no digits and no "%", for the window probes.
_FILLER = (" Further notes follow." * 20)


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


class TestTorrinBinaryExtractor(unittest.TestCase):

    def test_per_case_value_and_class(self):
        for cid, text, true_prob, exp_class, exp_value in CASES:
            with self.subTest(case=cid):
                value = torrin_binary(text)
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
            tally[classify(torrin_binary(text), true_prob)] += 1
        # Torrin44/forecast-bot's deterministic binary stage on this corpus,
        # identical case by case to forecasting-tools (13/3/0/2/2):
        self.assertEqual(tally["correct"], 13)
        self.assertEqual(tally["miss"], 3)
        self.assertEqual(tally["wrong_value"], 0)
        self.assertEqual(tally["false_positive"], 2)
        self.assertEqual(tally["correct_reject"], 2)
        self.assertEqual(sum(tally.values()), 20)

    def test_fallback_reads_unlabeled_percentages(self):
        # The fallback fires on any unlabeled "%": the prose forecast is read,
        # and so are both reasoning-text traps.
        self.assertAlmostEqual(torrin_binary("My probability is 73%."), 0.73, places=9)
        self.assertAlmostEqual(
            torrin_binary("Historically about a 5% base rate, nothing else."),
            0.05, places=9)

    # Probes outside the corpus tally.

    def test_probe_window_hides_early_base_rate(self):
        # A base rate more than 300 characters before the end is not read.
        text = "Historically about a 5% base rate." + _FILLER
        self.assertGreater(len(text) - text.index("5%"), 300)
        self.assertIsNone(torrin_binary(text))

    def test_probe_window_cuts_a_number(self):
        # The 300-character slice can start mid-number: "45%" is read as 5%.
        tail = "5%" + _FILLER[:298]
        text = "Final answer 4" + tail
        self.assertEqual(len(tail), 300)
        self.assertAlmostEqual(torrin_binary(text), 0.05, places=9)

    def test_probe_stale_labeled_draft_beats_unlabeled_final(self):
        text = ("Initial probability: 40%\n"
                "After weighing the evidence I settle on 55%.")
        self.assertAlmostEqual(torrin_binary(text), 0.40, places=9)

    def test_probe_out_of_range_and_commas(self):
        self.assertIsNone(torrin_binary("Probability: 150%"))
        self.assertIsNone(torrin_binary("Probability: 1,000%"))
        self.assertAlmostEqual(torrin_binary("Probability: 100%"), 1.0, places=9)


if __name__ == "__main__":
    unittest.main()
