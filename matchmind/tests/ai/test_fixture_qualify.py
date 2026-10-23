"""Fixture qualification: the data requirement as executable numbers.

Role C cannot edit Role B's fixtures. This pins what a fixture must satisfy so B has a target
and a regression check, and it keeps the shipped fixture's failures visible rather than letting
them be quietly forgotten.
"""
import unittest
from pathlib import Path

from evaluation.fixture_qualify import (THRESHOLDS, qualify, recommend_windows,
                                        summary_of_recommendations)

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "extra" / "validated-demo"


class ThresholdTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = qualify(DATA)
        cls.checks = {c["check"]: c for c in cls.result["matches"][0]["checks"]}

    def test_the_shipped_fixture_is_too_sparse_and_this_test_says_so(self):
        """If a denser fixture lands, this test should be updated to assert it passes. It is
        written as an assertion about today's data on purpose: silence would hide the gap."""
        self.assertFalse(self.result["summary"]["fixture_passes"])
        self.assertIn("seconds_per_event", self.result["summary"]["blocking"])
        self.assertGreater(self.checks["seconds_per_event"]["observed"],
                           THRESHOLDS["max_seconds_per_event"])

    def test_both_rosters_are_incomplete(self):
        self.assertIn("roster_home", self.result["summary"]["blocking"])
        self.assertIn("roster_away", self.result["summary"]["blocking"])
        self.assertLess(self.checks["roster_home"]["observed"],
                        THRESHOLDS["min_players_per_team"])

    def test_goal_accounting_is_consistent(self):
        self.assertTrue(self.checks["goal_accounting"]["passed"],
                        "the one thing the fixture does get right")

    def test_event_type_coverage_passes(self):
        self.assertTrue(self.checks["event_types"]["passed"])

    def test_every_check_carries_its_requirement(self):
        for check in self.checks.values():
            self.assertIn("required", check)
            self.assertIn("note", check)


class RecommendationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.candidates = recommend_windows(DATA)

    def test_a_window_exists_that_fires_and_contains_the_outcome(self):
        """The precise fix for PLAN_REVIEW 3.2: the problem is the chosen window, not the
        horizon, so a different window of the same length solves it."""
        summary = summary_of_recommendations(self.candidates)
        self.assertGreaterEqual(summary["candidates_that_explain_an_outcome"], 1)
        best = summary["best"]
        self.assertIsNotNone(best)
        self.assertTrue(best["goals_in_window"])
        self.assertGreaterEqual(best["high_recoveries"], 3)
        self.assertGreaterEqual(best["linked_shots"], 2)

    def test_the_shipped_default_window_cannot_explain_the_goal(self):
        default = [c for c in self.candidates
                   if c["window"]["start_sec"] == 1500 and c["window"]["end_sec"] == 1650]
        self.assertTrue(default, "the shipped default window must still fire the detector")
        self.assertFalse(default[0]["explains_an_outcome"])
        self.assertEqual(default[0]["goals_in_window"], [])

    def test_the_best_window_starts_after_the_default(self):
        best = summary_of_recommendations(self.candidates)["best"]
        self.assertGreater(best["window"]["start_sec"], 1500)

    def test_explainable_windows_are_sorted_first(self):
        flags = [c["explains_an_outcome"] for c in self.candidates]
        self.assertEqual(flags, sorted(flags, reverse=True))


if __name__ == "__main__":
    unittest.main()
