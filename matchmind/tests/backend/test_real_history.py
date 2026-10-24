import hashlib
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from backend.data import Catalog
from data.generator.real_history import PACKAGE, ROOT, cache_directory, fetch_archive, verify


class RealHistoryTests(unittest.TestCase):
    def package(self, directory):
        target = Path(directory) / "research"
        shutil.copytree(PACKAGE, target)
        return target

    def rehash(self, package, relative):
        manifest = json.loads((package / "manifest.json").read_text(encoding="utf-8"))
        data = (package / relative).read_bytes()
        manifest["payload_files"][relative] = {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
        (package / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    def test_provided_data_is_complete_and_not_loadable_as_runtime_fixture(self):
        result = verify()
        self.assertEqual((result["full_match_events"], result["clip_events"]), (1768, 96))
        self.assertFalse(result["synthetic"])
        self.assertFalse(result["runtime_compatible"])
        self.assertEqual(result["model_calls"], 0)
        self.assertEqual(list(PACKAGE.rglob("*.match.json")), [])
        with self.assertRaisesRegex(ValueError, "No local match fixtures"):
            Catalog(PACKAGE)

    def test_hash_detects_changed_source_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            package = self.package(directory)
            file = package / "samples/wyscout-2499719.events.original.jsonl"
            file.write_bytes(file.read_bytes()+b"\n")
            with self.assertRaisesRegex(ValueError, "checksum"):
                verify(package)

    def test_clip_cannot_be_fabricated_even_after_local_rehash(self):
        with tempfile.TemporaryDirectory() as directory:
            package = self.package(directory)
            relative = "samples/wyscout-2499719.1H-1500-1800.original.jsonl"
            rows = [json.loads(line) for line in (package / relative).read_text().splitlines()]
            rows[0]["positions"][0]["x"] = 99
            (package / relative).write_text("".join(json.dumps(row)+"\n" for row in rows), encoding="utf-8")
            self.rehash(package, relative)
            with self.assertRaisesRegex(ValueError, "original closed-interval"):
                verify(package)

    def test_manifest_paths_and_runtime_label_cannot_escape_research_scope(self):
        for change in ({"payload_files": {"../outside": {}}}, {"synthetic": True},
                       {"runtime_compatible": True}):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as directory:
                package = self.package(directory)
                manifest = json.loads((package / "manifest.json").read_text())
                manifest.update(change)
                (package / "manifest.json").write_text(json.dumps(manifest))
                with self.assertRaises(ValueError):
                    verify(package)
        for directory in (ROOT/"data/fixtures", ROOT/"data/extra", ROOT/"ai", ROOT/"frontend"):
            with self.subTest(directory=directory), self.assertRaises(ValueError):
                cache_directory(directory)

    def spec(self, data):
        return {"file": "events.zip", "source": "https://ndownloader.figshare.com/files/14464685",
                "bytes": len(data), "md5": hashlib.md5(data).hexdigest(),
                "sha256": hashlib.sha256(data).hexdigest()}

    def test_download_is_checked_atomic_and_correct_cache_is_reused(self):
        data = b"local fake source bytes"
        with tempfile.TemporaryDirectory() as directory, patch(
                "data.generator.real_history.urlopen", return_value=io.BytesIO(data)) as network:
            self.assertEqual(fetch_archive(self.spec(data), directory)["status"], "downloaded_and_verified")
            self.assertEqual(fetch_archive(self.spec(data), directory)["status"], "verified_cached")
            self.assertEqual(network.call_count, 1)
            self.assertEqual((Path(directory)/"events.zip").read_bytes(), data)
        with tempfile.TemporaryDirectory() as directory, patch(
                "data.generator.real_history.urlopen", return_value=io.BytesIO(b"wrong")):
            with self.assertRaisesRegex(ValueError, "checksum"):
                fetch_archive(self.spec(data), directory)
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_existing_different_file_is_preserved_and_unknown_download_host_rejected(self):
        with tempfile.TemporaryDirectory() as directory, patch("data.generator.real_history.urlopen") as network:
            target = Path(directory)/"events.zip"
            target.write_bytes(b"preserve")
            with self.assertRaisesRegex(ValueError, "preserve"):
                fetch_archive(self.spec(b"expected"), directory)
            self.assertEqual(target.read_bytes(), b"preserve")
            spec = self.spec(b"expected")
            spec["source"] = "https://example.invalid/not-the-source"
            with self.assertRaises(ValueError):
                fetch_archive(spec, directory)
            network.assert_not_called()
