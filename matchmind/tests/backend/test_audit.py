import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from backend.audit import ROOT, audit_dataset
from data.generator.prepare_demo import contents

GOLDEN = ROOT / "data/extra/validated-demo"


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.target = Path(self.temp.name)
        for file in GOLDEN.glob("*.json*"):
            shutil.copyfile(file, self.target / file.name)

    def rows(self):
        return [json.loads(row) for row in (self.target / "demo.events.jsonl").read_text().splitlines() if row]

    def write_rows(self, rows):
        (self.target / "demo.events.jsonl").write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
        # Recompute integrity to test the independent relationship/baseline checks.
        path = self.target / "PROVENANCE.json"
        meta = json.loads(path.read_text(encoding="utf-8"))
        meta["artifact_sha256"]["demo.events.jsonl"] = hashlib.sha256((self.target / "demo.events.jsonl").read_bytes()).hexdigest()
        path.write_text(json.dumps(meta), encoding="utf-8")

    def codes(self):
        return {issue["code"] for issue in audit_dataset(self.target)["issues"]}

    def test_preparation_is_byte_reproducible_and_keeps_frozen_source(self):
        source = ROOT / "data/fixtures/demo.events.jsonl"
        before = source.read_bytes()
        first, second = contents(), contents()
        self.assertEqual(first, second)
        self.assertEqual(source.read_bytes(), before)
        for name, value in first.items():
            self.assertEqual(value, (GOLDEN / name).read_bytes())
        original = [json.loads(row) for row in before.splitlines()]
        updated = [json.loads(row) for row in first["demo.events.jsonl"].splitlines()]
        self.assertEqual(original[:20], updated[:20])
        changed = [(a["event_id"], {k for k in a if a[k] != b[k]}) for a, b in zip(original, updated) if a != b]
        self.assertEqual(changed, [("MM-DEMO-01-E023", {"player_id"})])

    def test_corrected_dataset_passes(self):
        report = audit_dataset(self.target)
        self.assertEqual(report["status"], "passed", report)
        self.assertEqual(report["matches"][0]["events"], 30)

    def test_wrong_scorer_and_missing_goal_fail_even_after_rehash(self):
        rows = self.rows()
        rows[22]["player_id"] = "H02"
        self.write_rows(rows)
        self.assertIn("GOAL_RELATION", self.codes())
        self.write_rows([row for row in rows if row["type"] != "goal"])
        self.assertIn("SCORING_SHOT_RELATION", self.codes())

    def test_unknown_roster_member_fails_even_with_consistent_team(self):
        rows = self.rows()
        for row in rows:
            if row["player_id"] == "H01":
                row["player_id"] = "H99"
        self.write_rows(rows)
        self.assertIn("PLAYER_NOT_IN_ROSTER", self.codes())

    def test_changed_counts_fail_independent_baseline(self):
        rows = self.rows()
        rows[0]["outcome"] = "failed"
        self.write_rows(rows)
        self.assertIn("STATE_BASELINE_MISMATCH", self.codes())

    def test_hash_drift_and_duplicate_rows_fail(self):
        with (self.target / "roster.json").open("a", encoding="utf-8") as output:
            output.write("\n")
        self.assertIn("DATA_HASH_MISMATCH", self.codes())
        rows = self.rows()
        self.write_rows([*rows, rows[0]])
        self.assertIn("DUPLICATE_EVENT", self.codes())

    def test_bad_json_returns_a_failed_readiness_report(self):
        (self.target / "demo.events.jsonl").write_text("not json", encoding="utf-8")
        self.assertEqual(audit_dataset(self.target)["status"], "failed")

    def test_malformed_metadata_fails_instead_of_crashing(self):
        for name in ("roster.json", "expected.json", "PROVENANCE.json"):
            path = self.target / name
            original = path.read_bytes()
            for value in ("[]", "null"):
                with self.subTest(name=name, value=value):
                    path.write_text(value, encoding="utf-8")
                    self.assertIn("INVALID_METADATA", self.codes())
            path.write_bytes(original)
