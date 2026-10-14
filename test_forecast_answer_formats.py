"""Reproducibility test for the cross-tool binary answer-format corpus.

This recomputes every binary case in xtool_answer_formats.json from the
self-contained reference_extractors (transcribed from each tool's published
source) and asserts the per-case classes and the headline tallies stored in the
dataset are exactly right. The publish lane runs this before committing, so the
dataset's headline claim is execution-verified at publication time, with no
network and no third-party installs.

Made with AI by MV2 of Munim, Inc. (research field). Apache-2.0.
"""
import json
import os
import unittest

import reference_extractors as rx

HERE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(HERE, "xtool_answer_formats.json"), encoding="utf-8") as fh:
    DATA = json.load(fh)


class BinaryCorpus(unittest.TestCase):
    def test_each_case_matches_source_transcription(self):
        for c in DATA["binary"]:
            mv2 = rx.mv2_binary(c["text"])
            ft = rx.forecasting_tools_binary(c["text"])
            self.assertEqual(
                rx.classify(mv2, c["true_prob"]), c["mv2_class"],
                msg=f"mv2 class mismatch on {c['id']} ({c['text']!r}): got {mv2}")
            self.assertEqual(
                rx.classify(ft, c["true_prob"]), c["ft_class"],
                msg=f"ft class mismatch on {c['id']} ({c['text']!r}): got {ft}")
            # stored value matches recomputed value (within float tolerance)
            self._same_value(mv2, c["mv2_value"], c["id"], "mv2")
            self._same_value(ft, c["ft_value"], c["id"], "ft")

    def _same_value(self, got, stored, cid, which):
        if stored is None:
            self.assertIsNone(got, msg=f"{which} value on {cid} should be None, got {got}")
        else:
            self.assertIsNotNone(got, msg=f"{which} value on {cid} should be {stored}, got None")
            self.assertAlmostEqual(got, stored, places=9,
                                   msg=f"{which} value mismatch on {cid}")

    def test_headline_tallies(self):
        for tool, key in (("mv2_forecaster", "mv2_class"),
                           ("forecasting_tools", "ft_class")):
            tally = {}
            for c in DATA["binary"]:
                tally[c[key]] = tally.get(c[key], 0) + 1
            stored = DATA["binary_tally"][tool]
            # every stored bucket is reproduced exactly; no extra buckets appear
            self.assertEqual(tally.get("wrong_value", 0), 0,
                             msg=f"{tool} produced a wrong_value case")
            for bucket, n in stored.items():
                self.assertEqual(tally.get(bucket, 0), n,
                                 msg=f"{tool} {bucket}: expected {n}, got {tally.get(bucket, 0)}")
            self.assertEqual(sum(stored.values()), len(DATA["binary"]),
                             msg=f"{tool} tally does not sum to corpus size")

    def test_key_cross_tool_contrasts(self):
        by_id = {c["id"]: c for c in DATA["binary"]}
        # forecasting-tools drops dropped-% / bare-fraction / no-% answers mv2 reads
        for cid in ("bin_dropped_pct", "bin_bare_fraction", "bin_boundary_100"):
            self.assertEqual(by_id[cid]["mv2_class"], "correct")
            self.assertEqual(by_id[cid]["ft_class"], "miss")
        # mv2 drops non-colon / prose forecasts forecasting-tools reads
        for cid in ("bin_equals", "bin_prose_is"):
            self.assertEqual(by_id[cid]["mv2_class"], "miss")
            self.assertEqual(by_id[cid]["ft_class"], "correct")
        # forecasting-tools turns a base rate / prose % into a spurious forecast;
        # mv2 (label-gated) does not
        for cid in ("bin_baserate_only", "bin_two_prose_pcts"):
            self.assertEqual(by_id[cid]["mv2_class"], "correct_reject")
            self.assertEqual(by_id[cid]["ft_class"], "false_positive")


class DatasetShape(unittest.TestCase):
    def test_license_and_disclosure(self):
        self.assertEqual(DATA["license"], "CC BY 4.0")
        self.assertIn("AI", DATA["made_with"])

    def test_no_missing_fields(self):
        for c in DATA["binary"]:
            for k in ("id", "family", "text", "true_prob",
                      "mv2_value", "mv2_class", "ft_value", "ft_class"):
                self.assertIn(k, c, msg=f"{c.get('id')} missing {k}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
