# SPDX-License-Identifier: Apache-2.0
# Part of forecast-answer-formats, by MV2 of Munim, Inc. Made with AI.
#
# Self-contained: imports only eskemo_mc + the standard library, so the publish
# lane can run it with just these two files present (run-17 lesson). The 11
# multiple-choice cases are the same corpus as xtool_mc_formats.json; here we
# add the third extractor's per-case class and the aggregate tally, computed by
# hand-tracing the documented algorithm and asserted against the
# implementation. The probes at the end are NOT part of the corpus tally; they
# pin down two behaviours the write-up relies on.

import unittest

from eskemo_mc import extract_mc

OPTIONS = ["Option A", "Option B"]
INTENDED = {"Option A": 0.30, "Option B": 0.70}
TOL = 0.02

# (id, text, intended_or_None, expected_class)
CASES = [
    ("canonical", "Option A: 30%\nOption B: 70%", INTENDED, "correct"),
    ("no_percent", "Option A: 30\nOption B: 70", INTENDED, "correct"),
    ("decimal", "Option A: 0.30\nOption B: 0.70", INTENDED, "correct"),
    ("dash_bullet", "- Option A: 30%\n- Option B: 70%", INTENDED, "correct"),
    ("bold_label", "**Option A**: 30%\n**Option B**: 70%", INTENDED,
     "correct"),
    ("bold_colon_inside", "**Option A:** 30%\n**Option B:** 70%", INTENDED,
     "correct"),
    ("numbered", "1. Option A: 30%\n2. Option B: 70%", INTENDED, "correct"),
    ("pipe_table", "Option A | 30\nOption B | 70", INTENDED, "miss"),
    ("equals_separator", "Option A = 30%\nOption B = 70%", INTENDED,
     "correct"),
    ("parenthetical", "Option A (30%)\nOption B (70%)", INTENDED, "miss"),
    ("base_rate_table_trap",
     "For reference, here are last year's frequencies, which are NOT my "
     "forecast:\nOption A | 12\nOption B | 88\nI don't have enough "
     "information to forecast this question.",
     None, "correct_reject"),
]


def classify(result, expected):
    """Map an extractor's output to one of the five classes."""
    if expected is None:
        return "correct_reject" if result is None else "false_positive"
    if result is None:
        return "miss"
    if set(result) != set(expected):
        return "wrong_value"
    if all(abs(result[k] - expected[k]) <= TOL for k in expected):
        return "correct"
    return "wrong_value"


class TestEskemoMultipleChoiceExtractor(unittest.TestCase):

    def test_per_case_class(self):
        for cid, text, intended, exp_class in CASES:
            with self.subTest(case=cid):
                got = classify(extract_mc(text, OPTIONS), intended)
                self.assertEqual(got, exp_class, msg="%s: wrong class" % cid)

    def test_published_tally(self):
        tally = {"correct": 0, "miss": 0, "wrong_value": 0,
                 "false_positive": 0, "correct_reject": 0}
        for _cid, text, intended, _exp in CASES:
            tally[classify(extract_mc(text, OPTIONS), intended)] += 1
        # EskemoMan's multiple-choice extractor on this 11-case corpus:
        self.assertEqual(tally, {"correct": 8, "miss": 2, "wrong_value": 0,
                                 "false_positive": 0, "correct_reject": 1})

    def test_only_tool_that_reads_equals_separator(self):
        # Both mv2-forecaster and forecasting-tools drop "Option A = 30%".
        got = extract_mc("Option A = 30%\nOption B = 70%", OPTIONS)
        self.assertIsNotNone(got)
        self.assertAlmostEqual(got["Option A"], 0.30)

    def test_bare_pipe_dropped_but_leading_pipe_read(self):
        # A table row counts only if the line STARTS with '|'.
        self.assertIsNone(extract_mc("Option A | 30\nOption B | 70", OPTIONS))
        got = extract_mc("| Option A | 30 |\n| Option B | 70 |", OPTIONS)
        self.assertIsNotNone(got)
        self.assertAlmostEqual(got["Option B"], 0.70)

    def test_probe_no_reasoning_guard_on_leading_pipe_table(self):
        # The corpus trap is rejected only because its table lacks a leading
        # '|'. The same declined reference table written with leading pipes is
        # read as a forecast: like the numeric path, the MC path has no
        # reasoning-text guard.
        trap = ("For reference, here are last year's frequencies, which are "
                "NOT my forecast:\n| Option A | 12 |\n| Option B | 88 |\n"
                "I don't have enough information to forecast this question.")
        got = extract_mc(trap, OPTIONS)
        self.assertIsNotNone(got)
        self.assertAlmostEqual(got["Option A"], 0.12)

    def test_probe_incomplete_final_block_falls_back_to_reasoning(self):
        # The final answer names only one option, so there is no complete
        # forecast. The parser skips that block and returns an EARLIER complete
        # block from the reasoning (last year's split) instead of dropping.
        text = ("Last year's split was:\nOption A: 12%\nOption B: 88%\n"
                "This year conditions changed a lot.\n"
                "I am unsure about the rest.\n"
                "Final answer:\nOption A: 40%")
        got = extract_mc(text, OPTIONS)
        self.assertIsNotNone(got)
        self.assertAlmostEqual(got["Option A"], 0.12)
        self.assertAlmostEqual(got["Option B"], 0.88)

    def test_never_injects_a_default(self):
        self.assertIsNone(extract_mc("I can't forecast this.", OPTIONS))
        self.assertIsNone(extract_mc("Option A: 30%", OPTIONS))
        self.assertIsNone(extract_mc("Option A: 30%\nOption B: 30%", OPTIONS))


if __name__ == "__main__":
    unittest.main(verbosity=2)
