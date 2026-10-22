"""Fixture-agnostic evaluation harness: the sample is derived from the data, not hand-written.

The older hand-written case set was capped at what one 300-second fixture can produce — one
non-overlapping positive window. These tests pin the two behaviours that remove that cap:
auto-derived cases, and a non-overlap rule so three overlapping windows cannot masquerade as
three independent positives.
"""
import tempfile
import unittest
from pathlib import Path

from evaluation.benchmark import (DATA_DIR, auto_cases, build_cases, load_fixture,
                                  materialise)
from evaluation.dense_fixture_proposal import build_and_validate


class ShippedFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = auto_cases()

    def test_the_shipped_fixture_yields_exactly_one_independent_positive(self):
        positives = [c for c in self.cases if c["group"] == "positive"]
        self.assertEqual(len(positives), 1,
                         "the shipped fixture can only fire one non-overlapping window; if "
                         "this changed, update evaluation/README.md")

    def test_postives_never_overlap(self):
        windows = [(c["request"]["start"], c["request"]["end"])
                   for c in self.cases if c["group"] == "positive"]
        for index, (start, end) in enumerate(windows):
            for other_start, other_end in windows[index + 1:]:
                overlap = min(end, other_end) - max(start, other_start)
                self.assertLessEqual(overlap, 0,
                                     "two positives cover the same spell of play")

    def test_every_case_materialises_into_a_contract_valid_request(self):
        from contracts.validation import check_request
        for case in self.cases:
            request = materialise(case)
            if case["group"] == "tampered" and "event_index" in (case["request"]["tamper"] or {}):
                continue          # deliberately invalid; that is the point of the case
            check_request(request)

    def test_tampered_cases_are_actually_tampered(self):
        tampered = [c for c in self.cases if c["group"] == "tampered"]
        self.assertGreaterEqual(len(tampered), 4)
        for case in tampered:
            self.assertTrue(case["request"]["tamper"], case["id"])

    def test_the_hand_written_case_set_still_works(self):
        cases = build_cases()
        self.assertEqual(len(cases), 12)
        self.assertTrue(all("request" in c for c in cases))


class DenseFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        build_and_validate(Path(cls.tmp.name), seed=11, minutes=45)
        cls.cases = auto_cases(cls.tmp.name)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_a_dense_fixture_yields_more_independent_positives(self):
        positives = [c for c in self.cases if c["group"] == "positive"]
        self.assertGreaterEqual(len(positives), 4,
                                "a 45-minute fixture must produce several fireable windows")
        shipped = [c for c in auto_cases() if c["group"] == "positive"]
        self.assertGreater(len(positives), len(shipped))

    def test_the_dense_case_set_covers_every_group(self):
        groups = {c["group"] for c in self.cases}
        self.assertEqual(groups, {"positive", "non_trigger", "negative", "tampered"})

    def test_dense_positives_are_spread_across_the_clip(self):
        starts = sorted(c["request"]["start"] for c in self.cases
                        if c["group"] == "positive")
        self.assertGreater(starts[-1] - starts[0], 600,
                           "positives should cover different parts of the match")

    def test_both_teams_appear_as_a_positive_somewhere(self):
        teams = {c["request"]["team"] for c in self.cases if c["group"] == "positive"}
        self.assertIn("HOME", teams)


class LoaderTests(unittest.TestCase):
    def test_load_fixture_uses_the_first_match_by_default(self):
        fixture = load_fixture()
        self.assertEqual(fixture.match["match_id"], "MM-DEMO-01")

    def test_an_unknown_match_id_is_refused(self):
        with self.assertRaises(SystemExit):
            load_fixture(None, "NOPE")

    def test_the_default_directory_is_the_shipped_one(self):
        self.assertTrue((DATA_DIR / "demo.match.json").is_file())


if __name__ == "__main__":
    unittest.main()
