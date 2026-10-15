"""
Offline, deterministic recomputation of the multiple-choice cross-tool leg.

For every case in xtool_mc_formats.json this runs both reference extractors
(mc_extractors.mv2_mc / forecasting_tools_mc), classifies the result against the
case's intended distribution, and asserts:
  1. the computed class == the label stored in the corpus, and
  2. the per-extractor tally == the published mc_tally.

Because the reference extractors and the labels are both derived from each tool's
published source, a passing test proves internal consistency (no transcription
typo); the INDEPENDENT check against the live packages is the queued
mc-xtool-verify sandbox run. Run: python -m unittest -v

License: Apache-2.0. Made with AI, by MV2 of Munim, Inc.
"""
import json
import os
import unittest

from mc_extractors import mv2_mc, forecasting_tools_mc

_HERE = os.path.dirname(os.path.abspath(__file__))
TOL = 0.02


def _load():
    with open(os.path.join(_HERE, "xtool_mc_formats.json"), encoding="utf-8") as f:
        return json.load(f)


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


class MultipleChoiceCrossToolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = _load()
        cls.options = cls.data["options"]
        cls.extractors = {
            "mv2_forecaster": mv2_mc,
            "forecasting_tools": forecasting_tools_mc,
        }

    def test_each_case_matches_its_label(self):
        for case in self.data["multiple_choice"]:
            for name, fn in self.extractors.items():
                got = classify(fn(case["text"], self.options), case["expected"])
                want = case["labels"][name]
                self.assertEqual(
                    got, want,
                    msg=f"{name} on '{case['id']}': got {got}, label says {want}",
                )

    def test_tally_matches_published(self):
        for name, fn in self.extractors.items():
            tally = {c: 0 for c in self.data["classes"]}
            for case in self.data["multiple_choice"]:
                tally[classify(fn(case["text"], self.options), case["expected"])] += 1
            self.assertEqual(
                tally, self.data["mc_tally"][name],
                msg=f"recomputed tally for {name}: {tally}",
            )

    def test_two_clean_opposite_contrasts_exist(self):
        """mv2 reads where FT drops (numbered, bold-colon-inside); FT reads
        where mv2 drops (pipe_table). Guards the headline claim."""
        by_id = {c["id"]: c for c in self.data["multiple_choice"]}
        for cid in ("numbered", "bold_colon_inside"):
            self.assertIsNotNone(mv2_mc(by_id[cid]["text"], self.options))
            self.assertIsNone(forecasting_tools_mc(by_id[cid]["text"], self.options))
        self.assertIsNone(mv2_mc(by_id["pipe_table"]["text"], self.options))
        self.assertIsNotNone(
            forecasting_tools_mc(by_id["pipe_table"]["text"], self.options))

    def test_false_positive_trap(self):
        """FT reads a reference frequency table as a forecast; mv2 rejects it."""
        trap = next(c for c in self.data["multiple_choice"]
                    if c["id"] == "base_rate_table_trap")
        self.assertIsNone(mv2_mc(trap["text"], self.options))
        self.assertIsNotNone(forecasting_tools_mc(trap["text"], self.options))


if __name__ == "__main__":
    unittest.main(verbosity=2)
