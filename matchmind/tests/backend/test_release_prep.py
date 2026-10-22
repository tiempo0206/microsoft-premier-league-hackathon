import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from backend.audit import ROOT
from backend.showcase import build_packet, export_packet
from contracts.validation import check_request
from deploy.release_check import ai_checks, build_report, frontend_checks


class ReleasePrepTests(unittest.TestCase):
    def test_offline_packet_valid_inputs_and_separate_corruptions(self):
        packet = build_packet()
        self.assertEqual(packet["model_calls"], 0)
        self.assertEqual(len(packet["requests"]), 12)
        self.assertEqual(len(packet["tampered"]), 3)
        for request in packet["requests"]:
            check_request(request)
            self.assertLessEqual(max(e["timestamp_sec"] for e in request["events"]), request["window"]["end_sec"])
        # This case passes transport validation; C must independently refuse its arithmetic.
        check_request(packet["tampered"][0]["request"])
        for case in packet["tampered"][1:]:
            with self.assertRaises(ValueError):
                check_request(case["request"])

    def test_packet_exports_identically_with_verifiable_hashes_and_blocks_shared_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            names = export_packet(directory)["files"]
            first = {name: (directory / name).read_bytes() for name in names}
            export_packet(directory)
            self.assertEqual(first, {name: (directory / name).read_bytes() for name in names})
            manifest = json.loads(first["manifest.json"])
            for name, digest in manifest["artifact_sha256"].items():
                self.assertEqual(hashlib.sha256(first[name]).hexdigest(), digest)
        for destination in (ROOT/"contracts", ROOT/"ai", ROOT/"frontend", ROOT/"data/extra/showcase/press"):
            with self.subTest(destination=destination), self.assertRaises(ValueError):
                export_packet(destination)

    def test_backend_report_is_usable_without_model_credentials(self):
        with patch.dict(os.environ, {"MATCHMIND_SERVE_FRONTEND": "0",
                                     "MATCHMIND_MODEL_API_KEY": "never-print-this-placeholder"}):
            report = build_report("backend")
        self.assertEqual(report["status"], "passed")
        self.assertEqual(report["model_calls"], 0)
        self.assertNotIn("never-print", json.dumps(report))

    def test_integrated_profile_refuses_missing_C_and_A_artifacts(self):
        with tempfile.TemporaryDirectory() as temporary:
            report = build_report("integrated", ai_dir=Path(temporary), frontend_dist=Path(temporary))
        self.assertEqual(report["status"], "blocked")
        self.assertIn("C_composition_source", report["blocking"])
        self.assertIn("A_bundled_frontend_artifact", report["blocking"])
        self.assertFalse(report["model_endpoint_verified"])

    def test_local_frontend_references_need_real_assets_and_no_escape_or_CDN(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            entry = directory / "index.html"
            (directory / "assets").mkdir()
            (directory / "assets/app.js").write_text("/* verification artifact only */")
            entry.write_text('<script type="module" src="/assets/app.js"></script>')
            self.assertTrue(frontend_checks(directory))
            for bad in ('<script src="https://example.invalid/app.js"></script>',
                        '<script src="/assets/missing.js"></script>',
                        '<script src="../outside.js"></script>', '<h1>Placeholder</h1>'):
                entry.write_text(bad)
                self.assertFalse(frontend_checks(directory))
            entry.write_text('<script src="/assets/app.js"></script>')
            (directory / ".env").write_text("not-a-real-secret")
            self.assertFalse(frontend_checks(directory))

    def test_C_inspection_does_not_execute_C_code_or_install_dependencies(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            for name in ("app.py", "config.py", "provider.py", "verify.py"):
                (directory/name).write_text('raise RuntimeError("must never execute")\n')
            (directory/"service.py").write_text('async def analyze(request): return request\n')
            (directory/"requirements.txt").write_text("httpx==0.28.1\n")
            self.assertEqual(ai_checks(directory, version=lambda name: "0.28.1"), (True, True))
            self.assertEqual(ai_checks(directory, version=lambda name: "0.28.0"), (True, False))
            (directory/"service.py").write_text('def analyze(request): return request\n')
            self.assertEqual(ai_checks(directory), (False, False))

    def test_release_runner_stops_before_importing_C_when_not_ready(self):
        from deploy.release_run import main
        with patch("deploy.release_run.build_report", return_value={"status": "blocked"}), \
             patch("deploy.release_run.uvicorn.run") as server, patch("builtins.print"):
            with self.assertRaises(SystemExit) as context:
                main()
        self.assertEqual(context.exception.code, 2)
        server.assert_not_called()
