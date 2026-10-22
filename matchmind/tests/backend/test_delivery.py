import subprocess
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.audit import ROOT
from deploy.verify_backend import runtime_probe, verify_backend


class DeliveryTests(unittest.TestCase):
    def test_bad_data_stops_before_tests_or_listener(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch("deploy.verify_backend.build_report", return_value={"status": "failed"}), \
                 patch("deploy.verify_backend.run_checks") as checks, \
                 patch("deploy.verify_backend.runtime_probe") as listener:
                result = verify_backend(Path(tmp))
            self.assertEqual(result["status"], "failed")
            self.assertEqual(result["failed_stage"], "readiness")
            checks.assert_not_called()
            listener.assert_not_called()

    def test_shared_output_is_rejected_before_starting(self):
        with patch("deploy.verify_backend.runtime_probe") as listener:
            with self.assertRaises(ValueError):
                verify_backend(ROOT / "contracts")
            listener.assert_not_called()

    def test_owned_server_is_stopped_when_smoke_fails(self):
        children = []
        original = subprocess.Popen
        def start(*args, **kwargs):
            process = original(*args, **kwargs)
            if "uvicorn" in args[0]:
                children.append(process)
            return process
        with tempfile.TemporaryDirectory() as tmp:
            with patch("deploy.verify_backend.subprocess.Popen", side_effect=start), \
                 patch("deploy.verify_backend.probe", side_effect=ValueError("test smoke failure")):
                with self.assertRaisesRegex(ValueError, "test smoke failure"):
                    runtime_probe(Path(tmp))
        self.assertEqual(len(children), 1)
        self.assertIsNotNone(children[0].poll())

    def test_frontend_mode_is_rejected_without_starting_listener(self):
        with tempfile.TemporaryDirectory() as tmp, \
             patch.dict(os.environ, {"MATCHMIND_SERVE_FRONTEND": "1"}), \
             patch("deploy.verify_backend.runtime_probe") as listener:
            result = verify_backend(Path(tmp))
        self.assertEqual(result["failed_stage"], "readiness")
        listener.assert_not_called()
