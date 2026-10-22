import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.audit import ROOT
from backend.reporting import DEFAULT_DATA, build_analysis_report, canonical, export_analysis, output_directory
from contracts.validation import check_request


class ReportingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = build_analysis_report()

    def test_report_reconciles_independent_totals_and_source_events(self):
        report = self.report
        self.assertEqual(report["event_count"], 30)
        self.assertEqual(report["team_summary"]["HOME"]["pass_accuracy_percent"], 100)
        self.assertEqual(report["team_summary"]["AWAY"]["pass_accuracy_percent"], 76.92)
        self.assertEqual(report["team_summary"]["HOME"]["synthetic_possession_seconds"], 110)
        self.assertEqual(report["count_evidence_event_ids"]["HOME"]["score"], ["MM-DEMO-01-E023"])
        self.assertEqual(len(report["count_evidence_event_ids"]["HOME"]["shots"]), 3)
        self.assertEqual(report["invariants"]["logical_seconds_checked"], 301)
        self.assertTrue(report["primary_window"]["heuristic_eligible"])
        self.assertFalse(any(case["heuristic_eligible"] for case in report["negative_controls"]))
        segments = report["primary_window"]["possession_segments"]
        self.assertEqual(sum(s["end_sec"]-s["start_sec"] for s in segments if s["team_id"] == "HOME"), 35)
        self.assertEqual(sum(s["end_sec"]-s["start_sec"] for s in segments if s["team_id"] == "AWAY"), 115)
        self.assertEqual(report["checkpoints"][-1]["score"], {"HOME": 1, "AWAY": 0})

    def test_artifacts_are_reproducible_and_request_matches_frozen_contract(self):
        self.assertEqual(canonical(self.report), canonical(build_analysis_report()))
        changed = build_analysis_report()
        changed["limitations"].append("caller-local note")
        self.assertEqual(canonical(self.report), canonical(build_analysis_report()))
        request = self.report["analysis_request_example"]
        check_request(request)
        self.assertEqual(len(request["events"]), 20)
        self.assertEqual(request["metrics"]["home_possession_seconds"], 35)
        self.assertEqual(self.report["model_calls"], 0)
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            files = export_analysis(self.report, target)
            first = {name: (target / name).read_bytes() for name in files}
            export_analysis(self.report, target)
            self.assertEqual(first, {name: (target / name).read_bytes() for name in files})
            self.assertEqual(json.loads((target / "analysis-request.json").read_text(encoding="utf-8")), request)

    def test_corrupt_data_is_rejected_before_analysis(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            for source in DEFAULT_DATA.glob("*.json*"):
                shutil.copyfile(source, target / source.name)
            (target / "roster.json").write_text("null", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "audit failed"):
                build_analysis_report(target)

    def test_export_refuses_shared_and_other_role_paths(self):
        for target in (ROOT / "contracts", ROOT / "data/fixtures", ROOT / "frontend", ROOT.parent):
            with self.subTest(target=target), self.assertRaises(ValueError):
                export_analysis(self.report, target)

    def test_container_without_git_can_export_outside_app_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = Path(tmp) / "app"
            app.mkdir()
            with patch("backend.reporting.ROOT", app):
                self.assertEqual(output_directory(Path(tmp) / "reports"), (Path(tmp) / "reports").resolve())
