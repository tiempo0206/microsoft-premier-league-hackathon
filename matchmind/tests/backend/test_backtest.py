import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.backtest import jsonline, run_backtest
from backend.stats import state_at, window_metrics
from data.generator.scenarios import FAULTS, SOURCE, cases, fault_case, normal_case


class BacktestTests(unittest.TestCase):
    def test_seeds_and_serialized_cases_are_reproducible_and_disjoint(self):
        before = SOURCE.read_bytes()
        first = list(cases((1,), (1001,)))
        second = list(cases((1,), (1001,)))
        self.assertEqual(b"".join(map(jsonline, first)), b"".join(map(jsonline, second)))
        self.assertEqual(sum(case["kind"] == "normal" for case in first), 64)
        self.assertEqual(sum(case["kind"] == "invalid" for case in first), 72)
        development = {case["case_id"] for case in first if case["split"] == "development"}
        holdout = {case["case_id"] for case in first if case["split"] == "regression_holdout"}
        self.assertFalse(development & holdout)
        self.assertEqual(SOURCE.read_bytes(), before)
        for seeds in (((1,), (1,)), ((1,1), (1001,))):
            with self.assertRaises(ValueError):
                list(cases(*seeds))

    def test_reference_generation_does_not_call_the_implementation_under_test(self):
        with patch("backend.stats.state_at", side_effect=AssertionError("must not be oracle")), \
             patch("backend.stats.window_metrics", side_effect=AssertionError("must not be oracle")):
            case = normal_case(5, "positive", "HOME", "right", "development")
        self.assertEqual(case["expected"]["states"][-1]["score"], {"HOME": 1, "AWAY": 0})
        self.assertEqual(case["expected"]["metrics"]["high_recoveries"], 3)
        self.assertEqual(case["expected"]["metrics"]["linked_shots"], 2)

    def test_mirrored_team_cases_and_separate_fault_artifacts(self):
        normal = [normal_case(1, "positive", team, direction, "development")
                  for team in ("HOME", "AWAY") for direction in ("right", "left")]
        dataset = normal + [fault_case(normal[0], fault) for fault in FAULTS]
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            report = run_backtest(output, dataset)
            self.assertEqual(report["status"], "passed", report["results"])
            self.assertEqual(report["invalid_cases"], 9)
            self.assertEqual(report["splits"]["development"]["normal_cases"], 4)
            self.assertEqual(report["splits"]["development"]["unevaluated_normal_windows"], 0)
            self.assertEqual(report["direction_mirror_comparisons"], 2)
            self.assertEqual(report["team_swap_comparisons"], 2)
            normal_bytes = (output / "normal-scenarios.jsonl").read_bytes()
            invalid_bytes = (output / "invalid-cases.jsonl").read_bytes()
            self.assertTrue(all(json.loads(row)["kind"] == "normal" for row in normal_bytes.splitlines()))
            self.assertTrue(all(json.loads(row)["kind"] == "invalid" for row in invalid_bytes.splitlines()))
            self.assertEqual(hashlib.sha256(normal_bytes+invalid_bytes).hexdigest(), report["dataset_sha256"])
            self.assertEqual((output / "failing-cases.jsonl").read_bytes(), b"")

    def test_backtest_detects_lost_linked_shots_without_changing_the_oracle(self):
        dataset = [normal_case(1, "positive", "HOME", "right", "development"),
                   normal_case(1001, "cutoff_equal", "AWAY", "left", "regression_holdout")]
        def broken(*args, **kwargs):
            result = window_metrics(*args, **kwargs)
            result["linked_shots"] = 0
            return result
        with patch("backend.backtest.window_metrics", side_effect=broken):
            report = run_backtest(supplied_cases=dataset)
        self.assertEqual(report["status"], "failed")
        self.assertEqual(report["missed_triggers"], 2)
        self.assertEqual(report["splits"]["development"]["missed_triggers"], 1)
        self.assertEqual(report["splits"]["regression_holdout"]["missed_triggers"], 1)
        self.assertTrue(all("metric_oracle_mismatch" in row["issues"] for row in report["results"]))

    def test_backtest_detects_double_goal_counting(self):
        case = normal_case(1, "positive", "HOME", "right", "development")
        expected = copy.deepcopy(case["expected"])
        def broken(*args, **kwargs):
            result = state_at(*args, **kwargs)
            result["score"]["HOME"] *= 2
            return result
        with patch("backend.backtest.state_at", side_effect=broken):
            report = run_backtest(supplied_cases=[case])
        self.assertEqual(report["status"], "failed")
        self.assertIn("snapshot_oracle_mismatch", report["results"][0]["issues"])
        self.assertEqual(case["expected"], expected)
