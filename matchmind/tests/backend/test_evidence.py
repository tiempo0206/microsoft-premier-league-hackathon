import copy
import unittest

from backend.audit import ROOT
from backend.data import Catalog, Fixture
from backend.inputs import analysis_input
from backend.stats import high_press_detected, possession_segments, recovery_chains, state_at, window_metrics
from contracts.validation import check_request


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.fixture = Catalog(ROOT / "data/extra/validated-demo").fixtures["MM-DEMO-01"]

    def pair(self, delay=15, x=66.67, team="HOME", same_possession=True):
        recovery, shot = (copy.deepcopy(self.fixture.events[i]) for i in (6, 8))
        recovery.update(timestamp_sec=1560, team_id=team)
        recovery["position"]["x"] = x
        shot.update(timestamp_sec=1560 + delay, team_id=team,
                    possession_id=recovery["possession_id"] if same_possession else "OTHER")
        return Fixture(self.fixture.match, (recovery, shot))

    def test_actual_event_chains_and_negative_windows(self):
        chains = recovery_chains(self.fixture, 1500, 1650)
        self.assertEqual([c["recovery_event_id"] for c in chains],
                         ["MM-DEMO-01-E007", "MM-DEMO-01-E013", "MM-DEMO-01-E019"])
        self.assertEqual([[s["delay_sec"] for s in c["linked_shots"]] for c in chains], [[7], [9], []])
        self.assertEqual(chains[0]["evidence_event_ids"],
                         ["MM-DEMO-01-E007", "MM-DEMO-01-E008", "MM-DEMO-01-E009"])
        self.assertTrue(high_press_detected(window_metrics(self.fixture, 1500, 1650)))
        self.assertFalse(high_press_detected(window_metrics(self.fixture, 1500, 1559)))
        self.assertFalse(high_press_detected(window_metrics(self.fixture, 1500, 1650, "AWAY")))

    def test_time_position_direction_and_possession_boundaries(self):
        self.assertEqual(window_metrics(self.pair(), 1560, 1575)["linked_shots"], 1)
        self.assertEqual(window_metrics(self.pair(), 1560, 1574)["linked_shots"], 0)
        self.assertEqual(window_metrics(self.pair(delay=16), 1560, 1580)["linked_shots"], 0)
        self.assertEqual(window_metrics(self.pair(delay=0), 1560, 1580)["linked_shots"], 0)
        self.assertEqual(window_metrics(self.pair(x=66.669), 1560, 1580)["high_recoveries"], 0)
        self.assertEqual(window_metrics(self.pair(x=33.33, team="AWAY"), 1560, 1580, "AWAY")["linked_shots"], 1)
        self.assertEqual(window_metrics(self.pair(x=33.331, team="AWAY"), 1560, 1580, "AWAY")["high_recoveries"], 0)
        self.assertEqual(window_metrics(self.pair(same_possession=False), 1560, 1580)["linked_shots"], 0)
        fixture = self.pair(x=33.33)
        fixture.match["home_attack_direction"] = "left"
        self.assertEqual(window_metrics(fixture, 1560, 1580)["linked_shots"], 1)

    def test_multiple_shots_count_one_recovery(self):
        fixture = self.pair()
        second = copy.deepcopy(fixture.events[1])
        second.update(event_id="SECOND-SHOT", timestamp_sec=1574)
        rows = tuple(sorted([*fixture.events, second], key=lambda e: (e["timestamp_sec"], e["event_id"])))
        fixture = Fixture(fixture.match, rows)
        self.assertEqual(len(recovery_chains(fixture, 1560, 1580)[0]["linked_shots"]), 2)
        self.assertEqual(window_metrics(fixture, 1560, 1580)["linked_shots"], 1)

    def test_all_logical_seconds_preserve_count_and_time_invariants(self):
        previous = state_at(self.fixture, 1500)
        for sec in range(1500, 1801):
            state = state_at(self.fixture, sec)
            self.assertEqual(sum(state["possession_seconds"].values()), sec - 1500)
            for team in ("HOME", "AWAY"):
                self.assertLessEqual(state["score"][team], state["shots"][team])
                self.assertLessEqual(state["completed_passes"][team], state["passes"][team])
                for metric in ("score", "shots", "passes", "completed_passes", "possession_seconds"):
                    self.assertGreaterEqual(state[metric][team], previous[metric][team])
            previous = state

    def test_window_rejects_non_integer_reversed_and_out_of_clip_inputs(self):
        for start, end in ((True, 1650), (1500, 1650.5), (1500, 1499), (1499, 1650), (1500, 1801)):
            with self.subTest(start=start, end=end), self.assertRaises(ValueError):
                window_metrics(self.fixture, start, end)

    def test_ai_input_is_valid_and_cannot_mutate_source_events(self):
        request = analysis_input(self.fixture, task_id="OFFLINE-TASK", replay_id="OFFLINE-REPLAY", run_id=1)
        check_request(request)
        self.assertEqual(len(request["events"]), 20)
        self.assertEqual(request["metrics"]["linked_shots"], 2)
        request["events"][0]["position"]["x"] = -999
        self.assertEqual(self.fixture.events[0]["position"]["x"], 45)

    def test_possession_segments_use_observed_owner_and_half_open_boundaries(self):
        self.assertEqual(possession_segments(self.fixture, 1567, 1570), [
            {"start_sec": 1567, "end_sec": 1570, "team_id": "HOME", "source_event_id": "MM-DEMO-01-E009"}])
        self.assertEqual(possession_segments(self.fixture, 1570, 1571), [
            {"start_sec": 1570, "end_sec": 1571, "team_id": "AWAY", "source_event_id": "MM-DEMO-01-E010"}])
        self.assertEqual(possession_segments(self.fixture, 1570, 1570), [])
