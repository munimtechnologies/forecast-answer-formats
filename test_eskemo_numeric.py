# SPDX-License-Identifier: Apache-2.0
# Part of forecast-answer-formats, by MV2 of Munim, Inc. Made with AI.
#
# Self-contained: imports only eskemo_numeric + the standard library, so the
# publish lane can run it with just these two files present (run-17 lesson).
# The 8 numeric cases are the same corpus as xtool_numeric_formats.json; here we
# add the third extractor's per-case class, value and the aggregate tally,
# computed by hand-tracing the documented algorithm and asserted against the
# implementation.
#
# Modelling note: EskemoMan's parse_percentiles takes the question's declared
# percentile levels as `expected`. For each well-formed case we pass the levels
# of its intended distribution; for the trap case (no valid answer) we pass the
# standard [10, 50, 90] the question asked for. This matches how a harness would
# call it and how the other two tools are scored on this corpus.

import unittest

from eskemo_numeric import extract_numeric, classify_numeric

# (id, text, intended_map_or_None, declared_levels, expected_class)
CASES = [
    ("canonical_label",
     "Percentile 10: 100\nPercentile 50: 250\nPercentile 90: 500",
     {10: 100, 50: 250, 90: 500}, [10, 50, 90], "correct"),
    ("ordinal_wordorder",
     "10th percentile: 100\n50th percentile: 250\n90th percentile: 500",
     {10: 100, 50: 250, 90: 500}, [10, 50, 90], "correct"),
    ("markdown_bold_lines",
     "**Percentile 10:** 250\n**Percentile 50:** 500\n**Percentile 90:** 1000",
     {10: 250, 50: 500, 90: 1000}, [10, 50, 90], "correct"),
    ("comma_grouped_values",
     "Percentile 10: 1,000\nPercentile 50: 12,500\nPercentile 90: 125,000",
     {10: 1000, 50: 12500, 90: 125000}, [10, 50, 90], "correct"),
    ("negative_and_zero_values",
     "Percentile 10: -50\nPercentile 50: 0\nPercentile 90: 125",
     {10: -50, 50: 0, 90: 125}, [10, 50, 90], "correct"),
    ("currency_prefixed_values",
     "Percentile 10: $100\nPercentile 50: $250\nPercentile 90: $500",
     {10: 100, 50: 250, 90: 500}, [10, 50, 90], "correct"),
    ("two_percentiles_only",
     "Percentile 25: 100\nPercentile 75: 300",
     {25: 100, 75: 300}, [25, 75], "correct"),
    ("base_rate_block_then_declines",
     "Looking at base rates for this kind of event:\n"
     "10th percentile: 2\n50th percentile: 5\n90th percentile: 11\n"
     "These are last year's figures; I can't give calibrated percentiles "
     "for this year.",
     None, [10, 50, 90], "false_positive"),
]


class TestEskemoNumericExtractor(unittest.TestCase):

    def test_per_case_value_and_class(self):
        for cid, text, intended, levels, exp_class in CASES:
            with self.subTest(case=cid):
                got = extract_numeric(text, levels)
                self.assertEqual(classify_numeric(got, intended), exp_class,
                                 msg="%s: wrong class" % cid)
                if exp_class == "correct":
                    self.assertEqual(got, intended, msg="%s: wrong map" % cid)

    def test_published_tally(self):
        tally = {"correct": 0, "miss": 0, "wrong_value": 0,
                 "false_positive": 0, "correct_reject": 0}
        for _cid, text, intended, levels, _exp in CASES:
            tally[classify_numeric(extract_numeric(text, levels), intended)] += 1
        # EskemoMan's numeric extractor on this 8-case corpus:
        self.assertEqual(tally["correct"], 7)
        self.assertEqual(tally["miss"], 0)
        self.assertEqual(tally["wrong_value"], 0)
        self.assertEqual(tally["false_positive"], 1)
        self.assertEqual(tally["correct_reject"], 0)
        self.assertEqual(sum(tally.values()), 8)

    def test_reads_what_each_other_tool_drops(self):
        # Reads the "Nth percentile:" word order (mv2 drops it) ...
        self.assertIsNotNone(extract_numeric(
            "10th percentile: 100\n50th percentile: 250\n90th percentile: 500",
            [10, 50, 90]))
        # ... the markdown-bold block (forecasting-tools drops it) ...
        self.assertIsNotNone(extract_numeric(
            "**Percentile 10:** 250\n**Percentile 50:** 500\n"
            "**Percentile 90:** 1000", [10, 50, 90]))
        # ... and the 2-point answer (mv2 requires >= 3 percentiles).
        self.assertIsNotNone(extract_numeric(
            "Percentile 25: 100\nPercentile 75: 300", [25, 75]))

    def test_no_reasoning_guard_on_numeric(self):
        # Unlike its binary path (which rejects all reasoning-text traps),
        # the numeric path has no guard: it reads the base-rate block as a
        # forecast, the same false positive forecasting-tools commits.
        trap = ("Looking at base rates for this kind of event:\n"
                "10th percentile: 2\n50th percentile: 5\n90th percentile: 11\n"
                "These are last year's figures; I can't give calibrated "
                "percentiles for this year.")
        self.assertIsNotNone(extract_numeric(trap, [10, 50, 90]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
