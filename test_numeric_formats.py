# test_numeric_formats.py
# Execution-verifies the numeric (percentile) cross-tool leg at commit time:
# runs the source-grounded reference extractors over every labeled case and
# asserts each per-tool label and the published tallies. No network, no installs.
#
# Apache-2.0. Made with AI by MV2 of Munim, Inc.

import json
import os
import unittest

import numeric_extractors as nx

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "xtool_numeric_formats.json")


def _int_keys(m):
    if m is None:
        return None
    return {int(k): float(v) for k, v in m.items()}


def _blank():
    return {"correct": 0, "miss": 0, "false_positive": 0,
            "correct_reject": 0, "wrong_value": 0}


class NumericCrossToolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(DATA, encoding="utf-8") as fh:
            cls.corpus = json.load(fh)

    def test_each_case_matches_its_label(self):
        for case in self.corpus["cases"]:
            text = case["text"]
            intended = _int_keys(case["intended"])

            mv2 = nx.mv2_percentiles(text)
            self.assertEqual(
                nx.classify_percentiles(mv2, intended),
                case["expected"]["mv2_forecaster"],
                msg="mv2 label mismatch on %s" % case["id"],
            )

            ft_exp = case["expected"]["forecasting_tools"]
            if ft_exp is not None:
                ft = nx.ft_as_percentile_map(
                    nx.forecasting_tools_percentiles(text))
                self.assertEqual(
                    nx.classify_percentiles(ft, intended),
                    ft_exp,
                    msg="forecasting-tools label mismatch on %s" % case["id"],
                )

    def test_tallies_match_published(self):
        want = self.corpus["expected_tallies"]
        mv2_t, ft_t = _blank(), _blank()
        for case in self.corpus["cases"]:
            intended = _int_keys(case["intended"])
            mv2 = nx.mv2_percentiles(case["text"])
            mv2_t[nx.classify_percentiles(mv2, intended)] += 1
            if case["expected"]["forecasting_tools"] is not None:
                ft = nx.ft_as_percentile_map(
                    nx.forecasting_tools_percentiles(case["text"]))
                ft_t[nx.classify_percentiles(ft, intended)] += 1
        self.assertEqual(
            {k: mv2_t[k] for k in want["mv2_forecaster"]},
            want["mv2_forecaster"], msg="mv2 tally mismatch")
        self.assertEqual(
            {k: ft_t[k] for k in want["forecasting_tools"]},
            want["forecasting_tools"], msg="forecasting-tools tally mismatch")

    def test_known_contrasts_are_opposite(self):
        # The two headline contrasts must point in opposite directions.
        by_id = {c["id"]: c for c in self.corpus["cases"]}

        ordinal = by_id["ordinal_wordorder"]["text"]
        self.assertIsNone(nx.mv2_percentiles(ordinal))
        self.assertIsNotNone(nx.forecasting_tools_percentiles(ordinal))

        bold = by_id["markdown_bold_lines"]["text"]
        self.assertIsNotNone(nx.mv2_percentiles(bold))
        self.assertIsNone(nx.forecasting_tools_percentiles(bold))

        trap = by_id["base_rate_block_then_declines"]["text"]
        self.assertIsNone(nx.mv2_percentiles(trap))
        self.assertIsNotNone(nx.forecasting_tools_percentiles(trap))


if __name__ == "__main__":
    unittest.main(verbosity=2)
