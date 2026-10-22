"""The dense fixture proposal must keep proving the thresholds are achievable.

This is the counterweight to `test_fixture_qualify.py`, which asserts the *shipped* fixture
fails. Together they say: the requirement is real, and it is met by a generator in this
repository, so nobody has to guess what "dense enough" means.

The generator writes to a temporary directory, never to `data/fixtures/`: that directory and
`data/generator/` belong to Role B.
"""
import json
import tempfile
import unittest
from pathlib import Path

from evaluation.dense_fixture_proposal import (build_and_validate, generate,
                                               match_document, write)
from evaluation.fixture_qualify import THRESHOLDS, qualify, recommend_windows


class GeneratorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.events = generate(11)

    def test_it_is_dense_enough(self):
        span = 1800 - 1500
        seconds_per_event = span / len(self.events)
        self.assertLessEqual(seconds_per_event, THRESHOLDS["max_seconds_per_event"],
                             "%d events over %ds" % (len(self.events), span))

    def test_both_rosters_are_complete(self):
        players = {}
        for event in self.events:
            players.setdefault(event["team_id"], set()).add(event["player_id"])
        for team in ("HOME", "AWAY"):
            self.assertGreaterEqual(len(players[team]), THRESHOLDS["min_players_per_team"])

    def test_events_are_ordered_and_unique(self):
        keys = [(e["timestamp_sec"], e["event_id"]) for e in self.events]
        self.assertEqual(keys, sorted(keys))
        self.assertEqual(len({e["event_id"] for e in self.events}), len(self.events))

    def test_same_seed_produces_the_same_bytes(self):
        self.assertEqual(json.dumps(generate(11), sort_keys=True),
                         json.dumps(self.events, sort_keys=True))
        self.assertNotEqual(json.dumps(generate(12), sort_keys=True),
                            json.dumps(self.events, sort_keys=True))

    def test_a_possession_never_changes_team(self):
        owners = {}
        for event in self.events:
            owners.setdefault(event["possession_id"], event["team_id"])
            self.assertEqual(owners[event["possession_id"]], event["team_id"],
                             event["event_id"])

    def test_every_scoring_shot_has_exactly_one_goal(self):
        shots = [e for e in self.events if e["type"] == "shot" and e["outcome"] == "goal"]
        goals = [e for e in self.events if e["type"] == "goal"]
        self.assertEqual(len(shots), len(goals))
        self.assertEqual(len(goals), 1)
        for shot in shots:
            matching = [g for g in goals
                        if g["player_id"] == shot["player_id"]
                        and g["possession_id"] == shot["possession_id"]
                        and 0 <= g["timestamp_sec"] - shot["timestamp_sec"] <= 1]
            self.assertEqual(len(matching), 1, shot["event_id"])

    def test_no_foul_events_because_role_b_rejects_them(self):
        """The contract's Event.type enum allows "foul" but Role B's Fixture.load whitelist
        does not, so a generated foul is unusable. Reported, not silently skipped."""
        self.assertEqual([e for e in self.events if e["type"] == "foul"], [])

    def test_match_document_is_contract_shaped(self):
        from contracts.validation import check_shape
        check_shape("Match", match_document(len(self.events)))
        check_shape("Event", self.events[0])


class EndToEndTests(unittest.TestCase):
    def test_the_generated_fixture_passes_every_qualification_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = build_and_validate(Path(tmp), seed=11)
            self.assertEqual(report["problems"], [])
            self.assertEqual(report["warnings"], [])
            self.assertTrue(report["qualification"]["fixture_passes"],
                            report["qualification"])
            self.assertEqual(report["qualification"]["failed"], 0)

    def test_the_generated_fixture_has_windows_that_explain_an_outcome(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = build_and_validate(Path(tmp), seed=11)
            self.assertGreaterEqual(
                report["recommendations"]["candidates_that_explain_an_outcome"], 1)
            best = report["recommendations"]["best"]
            self.assertTrue(best["goals_in_window"])
            self.assertGreaterEqual(best["high_recoveries"], 3)
            self.assertGreaterEqual(best["linked_shots"], 2)

    def test_the_generated_fixture_loads_through_role_bs_own_loader(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = build_and_validate(Path(tmp), seed=11)
            self.assertIn("events", report)
            self.assertGreaterEqual(report["events"], 100)

    def test_qualify_and_recommend_agree_on_the_generated_fixture(self):
        with tempfile.TemporaryDirectory() as tmp:
            build_and_validate(Path(tmp), seed=11)
            self.assertTrue(qualify(Path(tmp))["summary"]["fixture_passes"])
            self.assertTrue(recommend_windows(Path(tmp)))

    def test_a_45_minute_half_produces_enough_moves_for_a_threat_grid(self):
        """Converts "expected threat needs a full match, not a clip" from a claim into a
        demonstration: the same generator, a longer span, and the grid stops refusing."""
        from ai.threat import rank_threat
        from backend.data import Catalog
        from backend.stats import window_events

        with tempfile.TemporaryDirectory() as tmp:
            events = generate(11, 1500, 4200)
            self.assertGreater(len(events), 900)
            write(Path(tmp), events, 11, 1500, 4200)
            fixture = Catalog(Path(tmp)).fixtures["DENSE-01"]
            loaded = window_events(fixture, 1500, 4200)
            result = rank_threat(loaded)
            self.assertTrue(result["available"], result.get("reason"))
            self.assertEqual(result["report"]["grid"], {"x": 16, "y": 12},
                             "a half supports the finest grid")
            self.assertGreater(result["report"]["transitions"], 500)
            self.assertIn("Not comparable to published xT", result["label"])

    def test_the_half_fixture_still_passes_qualification(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = build_and_validate(Path(tmp), seed=11, minutes=45)
            self.assertEqual(report["problems"], [])
            self.assertTrue(report["qualification"]["fixture_passes"])


if __name__ == "__main__":
    unittest.main()
