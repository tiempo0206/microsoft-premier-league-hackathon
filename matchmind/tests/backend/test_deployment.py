import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.app import create_app, ROOT
from backend.settings import Settings
from deploy.preflight import build_report


class DeploymentTests(unittest.TestCase):
    def command(self, *args, env=None, optimized=False):
        command = [sys.executable, *(["-O"] if optimized else []), "-m", "deploy.preflight", *args]
        return subprocess.run(command, cwd=ROOT, capture_output=True, encoding="utf-8", env=env, timeout=10)

    def test_preflight_uses_corrected_local_data_without_frontend_or_credentials(self):
        with patch.dict(os.environ, {"MATCHMIND_SERVE_FRONTEND": "0", "PORT": "8000"}):
            report = build_report()
        self.assertEqual(report["status"], "passed")
        self.assertEqual(report["runtime"]["workers"], 1)
        self.assertFalse(report["runtime"]["serve_frontend"])
        self.assertEqual(report["required_credentials"], [])
        self.assertEqual(report["data"]["matches"][0]["dataset_version"], "fixture-2.0.1")

    def test_invalid_original_data_fails_even_with_python_optimization(self):
        result = self.command("--data-dir", str(ROOT / "data/fixtures"), optimized=True)
        self.assertEqual(result.returncode, 2)
        report = json.loads(result.stdout)
        self.assertEqual(report["status"], "failed")
        self.assertIn("GOAL_RELATION", {x["code"] for x in report["data"]["issues"]})

    def test_report_file_is_written_only_when_requested_and_config_values_are_not_dumped(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.json"
            env = dict(os.environ, PORT="8000", MATCHMIND_MODEL_API_KEY="not-a-real-key-DO-NOT-LOG")
            result = self.command("--output", str(path), env=env)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["status"], "passed")
            self.assertNotIn("DO-NOT-LOG", result.stdout + result.stderr)
            env["PORT"] = "invalid-sensitive-value"
            result = self.command(env=env)
            self.assertEqual(result.returncode, 2)
            self.assertNotIn("invalid-sensitive-value", result.stdout + result.stderr)

    def test_corrupt_data_is_rejected_before_app_start(self):
        with self.assertRaisesRegex(ValueError, "Dataset readiness failed"):
            create_app(data_dir=ROOT / "data/fixtures", settings=Settings())

    def test_api_only_mode_does_not_mount_even_an_available_page(self):
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / "index.html").write_text("fixture supplied by an integration test", encoding="utf-8")
            app = create_app(frontend_dist=directory, settings=Settings(serve_frontend=False))
            self.assertNotIn("frontend", [getattr(route, "name", None) for route in app.routes])

    def test_invalid_settings_fail_early(self):
        for key, value in (("MATCHMIND_SERVE_FRONTEND", "yes"), ("MATCHMIND_MAX_REPLAY_SESSIONS", "0"), ("MATCHMIND_DATA_DIR", "")):
            with self.subTest(key=key), patch.dict(os.environ, {key: value}), self.assertRaises(ValueError):
                Settings.from_env()
