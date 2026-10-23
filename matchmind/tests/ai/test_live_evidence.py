"""Guards the committed live-model evidence against the two ways it could go wrong.

The evidence file exists so a reviewer can check a claim without trusting anyone. That only works if
the file stays (a) credential-free and (b) actually about a live model. Both are cheap to check
offline, so they are checked here rather than promised in a document.

The run itself is billable and is never part of the suite; these tests only read what was recorded.
"""
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "evaluation" / "evidence"
KEY_SHAPE = re.compile(r"sk-[A-Za-z0-9]{16,}")

REQUIRED = ("config", "request", "result", "contract", "publishable", "elapsed_ms",
            "model_calls_direct_provider", "model_calls_note", "provenance")


def records():
    """Every committed record. Missing directory is fine; an empty one is not asserted on."""
    if not EVIDENCE.is_dir():
        return []
    return sorted(p for p in EVIDENCE.glob("*.json"))


class EvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.files = records()
        cls.records = [(p, json.loads(p.read_text(encoding="utf-8"))) for p in cls.files]

    def test_there_is_at_least_one_record(self):
        """Acceptance criterion 5 needs one real explain-and-review pass, kept as evidence."""
        self.assertTrue(self.records, "no committed live-model evidence in evaluation/evidence/")

    def test_no_record_contains_a_credential(self):
        for path in self.files:
            text = path.read_text(encoding="utf-8")
            self.assertIsNone(KEY_SHAPE.search(text), path.name + " contains a key-shaped string")
            for banned in ("api_key", "Authorization", "Bearer "):
                self.assertNotIn(banned, text, path.name + " mentions " + banned)

    def test_every_record_carries_the_fields_a_reviewer_needs(self):
        for path, record in self.records:
            for field in REQUIRED:
                self.assertIn(field, record, path.name + " is missing " + field)
            self.assertIn("provenance", record)
            for field in ("recorded_utc", "git_head", "prompt_version", "contract_version"):
                self.assertIn(field, record["provenance"], path.name + " provenance lacks " + field)

    def test_a_recorded_card_is_a_verified_live_card_not_a_fallback(self):
        for path, record in self.records:
            insight = record["result"]
            generation = insight["generation"]
            self.assertEqual(generation["mode"], "live_model",
                             path.name + " is not a live-model run")
            self.assertTrue(generation["model"], path.name + " does not name its model")
            self.assertEqual(insight["verification"]["method"], "agent_and_code",
                             path.name + " was not reviewed by an agent and by code")
            self.assertEqual(insight["verification"]["status"], "passed")

    def test_the_orchestrator_is_named_in_the_trace(self):
        """`model_calls: 0` next to a live card is only readable if the trace says who called it."""
        for path, record in self.records:
            notes = [t.get("note", "") for t in record["result"]["traces"]]
            self.assertTrue(any(note.startswith("orchestrator=") for note in notes),
                            path.name + " does not record which orchestrator ran")

    def test_the_provider_counter_is_labelled_not_dressed_up(self):
        """A framework run never touches the direct provider, so the counter reads 0. The record has
        to say which counter that is, or it reads like 'no model was called'."""
        for path, record in self.records:
            self.assertIn("model_calls_direct_provider", record)
            if record["model_calls_direct_provider"] == 0:
                self.assertIn("Agent Framework", record["model_calls_note"], path.name)
                self.assertGreaterEqual(record["result"]["agent_invocations"], 1, path.name)

    def test_the_record_states_what_it_is_not(self):
        for path, record in self.records:
            note = record.get("note", "").lower()
            self.assertIn("not a benchmark", note, path.name)
            self.assertTrue(record["provenance"]["synthetic_data"], path.name)


if __name__ == "__main__":
    unittest.main()
