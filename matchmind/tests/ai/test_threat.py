"""Threat-added heuristic: correctness of the maths, and honesty about the data.

The interesting tests here are the refusals. An expected-threat grid computed from 70 moves is a
number that looks authoritative and means nothing, so the module must say no — and must say yes
when the sample is actually big enough.
"""
import random
import unittest

from ai.threat import (GRID_CANDIDATES, build_grid, collect_transitions, rank_threat,
                       threat_added, zone_of)


def synthetic_sample(n_possessions=400, seed=3):
    """A full-match-sized sample of ordinary play, built the same way a generator would."""
    rng = random.Random(seed)
    events = []
    clock = 1
    for _ in range(n_possessions):
        team = rng.choice(("HOME", "AWAY"))
        possession = "P%04d" % len(events)
        x = rng.uniform(10, 85)
        y = rng.uniform(10, 90)
        events.append({"event_id": "E%05d" % len(events), "match_id": "M", "timestamp_sec": clock,
                       "period": 1, "type": "pass", "team_id": team, "player_id": team[0] + "1",
                       "position": {"x": x, "y": y},
                       "end_position": {"x": min(99.0, x + rng.uniform(-5, 25)),
                                        "y": min(99.0, max(1.0, y + rng.uniform(-15, 15)))},
                       "outcome": "successful" if rng.random() < 0.8 else "failed",
                       "possession_id": possession})
        clock += 2
        if rng.random() < 0.18:
            events.append({"event_id": "E%05d" % len(events), "match_id": "M",
                           "timestamp_sec": clock, "period": 1, "type": "shot",
                           "team_id": team, "player_id": team[0] + "2",
                           "position": {"x": rng.uniform(75, 95), "y": rng.uniform(25, 75)},
                           "end_position": None,
                           "outcome": "goal" if rng.random() < 0.1 else "off_target",
                           "possession_id": possession})
            clock += 2
    return events


class GeometryTests(unittest.TestCase):
    def test_home_attacks_right_and_away_is_mirrored(self):
        near_goal = {"x": 95.0, "y": 50.0}
        self.assertEqual(zone_of(near_goal, True, (10, 10))[0], 9)
        self.assertEqual(zone_of(near_goal, False, (10, 10))[0], 0)

    def test_out_of_range_coordinates_are_clamped(self):
        self.assertEqual(zone_of({"x": 100.0, "y": 100.0}, True, (10, 10)), (9, 9))
        self.assertEqual(zone_of({"x": -5.0, "y": -5.0}, True, (10, 10)), (0, 0))

    def test_a_missing_point_is_not_a_zone(self):
        self.assertIsNone(zone_of(None))
        self.assertIsNone(zone_of({}))


class TransitionTests(unittest.TestCase):
    def test_only_completed_passes_count_as_moves(self):
        events = [
            {"type": "pass", "team_id": "HOME", "outcome": "successful",
             "position": {"x": 20, "y": 20}, "end_position": {"x": 40, "y": 20}},
            {"type": "pass", "team_id": "HOME", "outcome": "failed",
             "position": {"x": 20, "y": 20}, "end_position": {"x": 60, "y": 20}},
        ]
        moves, shots, goals = collect_transitions(events, (10, 10))
        self.assertEqual(sum(sum(r.values()) for r in moves.values()), 1)
        self.assertEqual(shots, {})

    def test_a_pass_within_one_zone_is_not_a_move(self):
        events = [{"type": "pass", "team_id": "HOME", "outcome": "successful",
                   "position": {"x": 21, "y": 21}, "end_position": {"x": 22, "y": 22}}]
        moves, _, _ = collect_transitions(events, (10, 10))
        self.assertEqual(moves, {})

    def test_goals_are_counted_only_from_goal_shots(self):
        events = [
            {"type": "shot", "team_id": "HOME", "outcome": "goal",
             "position": {"x": 90, "y": 50}},
            {"type": "shot", "team_id": "HOME", "outcome": "off_target",
             "position": {"x": 88, "y": 50}},
        ]
        _, shots, goals = collect_transitions(events, (10, 10))
        self.assertEqual(sum(shots.values()), 2)
        self.assertEqual(sum(goals.values()), 1)


class RefusalTests(unittest.TestCase):
    def test_the_shipped_fixture_is_refused(self):
        from backend.data import Catalog
        from backend.stats import window_events
        from pathlib import Path
        root = Path(__file__).resolve().parents[2]
        fixture = Catalog(root / "data" / "extra" / "validated-demo").fixtures["MM-DEMO-01"]
        result = rank_threat(window_events(fixture, 1500, 1800))
        self.assertFalse(result["available"])
        self.assertIn("too short", result["reason"])
        self.assertEqual(result["ranked"], [])
        self.assertTrue(result["report"]["resolution_trials"],
                        "the refusal must show which resolutions were tried")

    def test_a_sample_with_no_shots_is_refused(self):
        events = [{"type": "pass", "team_id": "HOME", "outcome": "successful",
                   "position": {"x": 10, "y": 10}, "end_position": {"x": 30, "y": 10}}
                  for _ in range(500)]
        grid, resolution, report = build_grid(events, min_per_cell=1)
        self.assertIsNone(grid)
        self.assertIn("no shots", report["refused"])

    def test_the_refusal_names_the_threshold_it_could_not_meet(self):
        grid, resolution, report = build_grid([], min_per_cell=4)
        self.assertIsNone(grid)
        self.assertEqual(report["min_observations_per_cell"], 4)


class GridTests(unittest.TestCase):
    def test_a_large_sample_produces_a_converged_grid(self):
        events = synthetic_sample()
        grid, resolution, report = build_grid(events)
        self.assertIsNotNone(grid, report.get("refused"))
        self.assertIn(resolution, GRID_CANDIDATES)
        self.assertGreater(report["converged_after"], 0)
        self.assertGreaterEqual(report["observations_per_cell"]
                                if "observations_per_cell" in report else 0, 0)
        self.assertTrue(all(0.0 <= v <= 1.0 + 1e-9 for v in grid.values()),
                        "zone values are probabilities of scoring from that zone")

    def test_close_to_goal_is_worth_more_than_deep_in_own_half(self):
        events = synthetic_sample()
        grid, resolution, _ = build_grid(events)
        self.assertIsNotNone(grid)
        cells_x, _ = resolution
        near = max(grid.get((cells_x - 1, y), 0.0) for y in range(resolution[1]))
        far = max(grid.get((0, y), 0.0) for y in range(resolution[1]))
        self.assertGreater(near, far,
                           "a grid that values the own half above the attacking box is broken")

    def test_ranking_returns_a_labelled_caveat(self):
        events = synthetic_sample()
        result = rank_threat(events)
        self.assertTrue(result["available"])
        self.assertIn("Not comparable to published xT", result["label"])
        self.assertIn("within-clip", result["caveat"])
        self.assertLessEqual(len(result["ranked"]), 5)
        values = [row["threat_added"] for row in result["ranked"]]
        self.assertEqual(values, sorted(values, reverse=True))

    def test_threat_added_is_none_for_failed_or_non_pass_events(self):
        events = synthetic_sample()
        grid, resolution, _ = build_grid(events)
        self.assertIsNone(threat_added({"type": "pass", "outcome": "failed"}, grid, resolution))
        self.assertIsNone(threat_added({"type": "shot", "outcome": "goal"}, grid, resolution))
        self.assertIsNone(threat_added({"type": "pass", "outcome": "successful"}, None, None))


if __name__ == "__main__":
    unittest.main()
