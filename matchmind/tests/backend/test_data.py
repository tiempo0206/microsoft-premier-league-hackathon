import copy
import json
import tempfile
import unittest
from pathlib import Path

from backend.app import ROOT
from backend.data import Catalog, Fixture
from backend.stats import state_at, window_metrics
from contracts.validation import check_shape


class DataTests(unittest.TestCase):
    def setUp(self):
        self.fixture = Catalog(ROOT / "data/fixtures").fixtures["MM-DEMO-01"]

    def load_rows(self, rows):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "test.match.json"
            path.write_text(json.dumps(self.fixture.match), encoding="utf-8")
            path.with_name("test.events.jsonl").write_text("\n".join(json.dumps(e) for e in rows), encoding="utf-8")
            return Fixture.load(path)

    def test_audited_totals_and_no_double_goal(self):
        middle = state_at(self.fixture, 1650)
        check_shape("MatchState", middle)
        self.assertEqual(middle["shots"], {"HOME": 2, "AWAY": 0})
        self.assertEqual(middle["passes"], {"HOME": 3, "AWAY": 10})
        self.assertEqual(middle["possession_seconds"], {"HOME": 35, "AWAY": 115})
        self.assertEqual(state_at(self.fixture, 1680)["score"]["HOME"], 0)
        self.assertEqual(state_at(self.fixture, 1681)["score"]["HOME"], 1)
        end = state_at(self.fixture, 1800)
        self.assertEqual(end["score"], {"HOME": 1, "AWAY": 0})
        self.assertEqual(end["shots"], {"HOME": 3, "AWAY": 1})
        self.assertEqual(end["possession_seconds"], {"HOME": 110, "AWAY": 190})

    def test_initial_and_time_conservation(self):
        for at in (1500, 1501, 1560, 1650, 1800):
            self.assertEqual(sum(state_at(self.fixture, at)["possession_seconds"].values()), at - 1500)
        self.assertIsNone(state_at(self.fixture, 1500)["last_event_id"])
        with self.assertRaises(ValueError):
            state_at(self.fixture, 1499)

    def test_window_counts_each_recovery_once_and_obeys_cutoff(self):
        metrics = window_metrics(self.fixture, 1500, 1650)
        self.assertEqual((metrics["high_recoveries"], metrics["linked_shots"]), (3, 2))
        self.assertEqual(window_metrics(self.fixture, 1500, 1559)["high_recoveries"], 0)
        shot = copy.deepcopy(self.fixture.events[8])
        shot.update(event_id="EXTRA-SHOT", timestamp_sec=1568)
        altered = Fixture(self.fixture.match, tuple(sorted([*self.fixture.events, shot], key=lambda e: (e['timestamp_sec'], e['event_id']))))
        self.assertEqual(window_metrics(altered, 1500, 1650)["linked_shots"], 2)

    def test_duplicate_identical_is_deduplicated_conflicting_is_rejected(self):
        rows = [*self.fixture.events, self.fixture.events[0]]
        self.assertEqual(len(self.load_rows(rows).events), 30)
        changed = copy.deepcopy(self.fixture.events[0])
        changed["outcome"] = "failed"
        with self.assertRaisesRegex(ValueError, "different content"):
            self.load_rows([*self.fixture.events, changed])

    def test_invalid_semantics_and_order_are_rejected(self):
        for change in ({"team_id": "OTHER"}, {"timestamp_sec": 1499}, {"player_id": "H08"},
                       {"end_position": None}, {"outcome": "goal"}):
            rows = copy.deepcopy(list(self.fixture.events))
            rows[0].update(change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.load_rows(rows)
        rows = list(self.fixture.events)
        rows[0], rows[1] = rows[1], rows[0]
        with self.assertRaisesRegex(ValueError, "ordered"):
            self.load_rows(rows)

    def test_known_frozen_scorer_mismatch_is_reported_not_silently_fixed(self):
        self.assertEqual(len(self.fixture.warnings), 1)
        self.assertIn("E023", self.fixture.warnings[0])
        self.assertEqual(self.fixture.events[22]["player_id"], "H02")


if __name__ == "__main__":
    unittest.main()
