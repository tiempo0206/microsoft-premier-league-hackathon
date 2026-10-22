import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from backend.audit import audit_dataset
from backend.data import Catalog
from backend.inputs import analysis_input
from backend.reporting import check_invariants
from backend.stats import state_at, window_metrics
from contracts.validation import check_request
from data.generator.showcase import SCENARIOS, contents, generate, reference_state
from deploy.preflight import build_report


class ShowcaseTests(unittest.TestCase):
    def prepare(self, directory, scenario, seed=20261023):
        for name, value in contents(scenario, seed).items():
            (directory / name).write_bytes(value)
        return next(iter(Catalog(directory).fixtures.values()))

    def test_deterministic_dense_connected_scripts_and_independent_states(self):
        for scenario in SCENARIOS:
            with self.subTest(scenario=scenario), tempfile.TemporaryDirectory() as temporary:
                directory = Path(temporary)
                self.assertEqual(contents(scenario), contents(scenario))
                fixture = self.prepare(directory, scenario)
                self.assertGreaterEqual(len(fixture.events), 100)
                self.assertEqual(audit_dataset(directory)["status"], "passed")
                self.assertEqual(build_report(data_dir=directory)["status"], "passed")
                match, events, ownership = generate(scenario)
                for at in range(1500, 1801):
                    self.assertEqual(state_at(fixture, at), reference_state(match, events, ownership, at))
                self.assertEqual(check_invariants(fixture)["status"], "passed")
                for team in ("HOME", "AWAY"):
                    self.assertEqual(len({e["player_id"] for e in events if e["team_id"] == team}), 11)
                for previous, current in zip(events, events[1:]):
                    if previous["type"] == "pass" and previous["possession_id"] == current["possession_id"]:
                        self.assertEqual(previous["end_position"], current["position"])

    def test_trigger_controls_goal_and_multilingual_requests(self):
        for scenario, expected in (("press", (3, 2)), ("delayed", (3, 0)), ("quiet", (0, 0))):
            with self.subTest(scenario=scenario), tempfile.TemporaryDirectory() as temporary:
                fixture = self.prepare(Path(temporary), scenario)
                metrics = window_metrics(fixture, 1500, 1650)
                self.assertEqual((metrics["high_recoveries"], metrics["linked_shots"]), expected)
                self.assertEqual(state_at(fixture, 1650)["score"]["HOME"], int(scenario == "press"))
                self.assertEqual(fixture.warnings, ())
                for language in ("en", "zh"):
                    request = analysis_input(fixture, replay_id="OFFLINE", run_id=1,
                                             task_id="OFFLINE-TEST", language=language)
                    check_request(request)

    def test_reference_is_not_derived_from_backend_and_rehash_does_not_hide_tampering(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            self.prepare(directory, "press")
            path = directory / "demo.events.jsonl"
            rows = [json.loads(row) for row in path.read_text().splitlines()]
            rows = [row for row in rows if row["type"] != "goal"]
            path.write_text("\n".join(json.dumps(row) for row in rows)+"\n", encoding="utf-8")
            manifest = json.loads((directory / "PROVENANCE.json").read_text())
            manifest["artifact_sha256"][path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
            manifest["event_count"] = len(rows)
            (directory / "PROVENANCE.json").write_text(json.dumps(manifest))
            codes = {issue["code"] for issue in audit_dataset(directory)["issues"]}
            self.assertIn("STATE_BASELINE_MISMATCH", codes)
            self.assertIn("SCORING_SHOT_RELATION", codes)
            self.assertEqual(build_report(data_dir=directory)["status"], "failed")

    def test_extra_seeds_keep_authored_football_and_trigger_invariants(self):
        for scenario in SCENARIOS:
            for seed in (1, 2, 1001, 1002):
                with self.subTest(scenario=scenario, seed=seed), tempfile.TemporaryDirectory() as temporary:
                    fixture = self.prepare(Path(temporary), scenario, seed)
                    self.assertEqual(build_report(data_dir=Path(temporary))["status"], "passed")
                    self.assertEqual(check_invariants(fixture)["status"], "passed")

    def test_bad_generator_parameters_are_rejected(self):
        for scenario, seed in (("other", 1), ("press", True), ("quiet", -1), ("quiet", 2**32)):
            with self.subTest(scenario=scenario, seed=seed), self.assertRaises(ValueError):
                generate(scenario, seed)
