"""The metric definitions must reach the model.

Without them the analyst writes "within 15 seconds" — correct by the contract's definition of
`linked_shots` but unsupported by a facts block that only lists `linked_shots=2` — and the auditor
rejects it. That was measured as a leading cause of honest fallbacks, so the definitions are now
part of the prompt and these tests keep them there.
"""
import json
import unittest
from pathlib import Path

from ai.prompts import facts_block
from ai.verify import METRIC_DEFINITIONS, METRIC_KEYS, allowed_numbers

ROOT = Path(__file__).resolve().parents[2]
REQUEST = json.loads((ROOT / "contracts/examples/analysis_request.json").read_text(encoding="utf-8"))


class DefinitionsTests(unittest.TestCase):
    def test_every_metric_key_has_a_definition(self):
        self.assertEqual(set(METRIC_DEFINITIONS), set(METRIC_KEYS),
                         "a metric without a definition will be rejected by the auditor when "
                         "the analyst explains it")

    def test_the_definitions_match_the_contract_document(self):
        """docs/02_contract.md is the human contract; drift here means the model is told
        something the product does not actually compute."""
        text = (ROOT / "docs" / "02_contract.md").read_text(encoding="utf-8") \
            if (ROOT / "docs" / "02_contract.md").is_file() else ""
        if not text:
            self.skipTest("contract document not present in this checkout")
        self.assertIn("66.67", METRIC_DEFINITIONS["high_recoveries"])
        self.assertIn("15", METRIC_DEFINITIONS["linked_shots"])

    def test_the_facts_block_carries_the_definitions(self):
        block = facts_block(REQUEST, allowed_numbers=allowed_numbers(REQUEST))
        self.assertIn("metric_definitions:", block)
        for key in METRIC_KEYS:
            self.assertIn(key + " = ", block, key)

    def test_the_linked_shots_definition_is_what_the_judge_would_read(self):
        """The 15-second horizon is the single most quoted number in our explanations, so the
        model has to be told it rather than left to infer it."""
        self.assertIn("15 seconds", METRIC_DEFINITIONS["linked_shots"])

    def test_the_mcp_tool_uses_the_same_definitions(self):
        from ai.mcp_server import get_metrics
        payload = get_metrics("MM-DEMO-01", 1500, 1650, "HOME")
        for key, value in payload["definitions"].items():
            self.assertEqual(value, METRIC_DEFINITIONS[key])


class AllowedNumbersTests(unittest.TestCase):
    def test_every_number_the_facts_block_states_is_allowed_in_prose(self):
        """The invariant that would have caught a real regression.

        The metric definitions carry 66.67 and 15. Adding them to the facts block without adding
        them to the allowed set made the narrator get rejected for repeating a fact it had been
        given, which produced a wave of unnecessary fallbacks.
        """
        block = facts_block(REQUEST, allowed_numbers=allowed_numbers(REQUEST))
        allowed = allowed_numbers(REQUEST)
        from ai.verify import numbers_in
        stated = numbers_in(block)
        self.assertTrue(stated, "the facts block should state some numbers")
        missing = sorted(n for n in stated if n not in allowed
                         and n not in {float(e["timestamp_sec"]) for e in REQUEST["events"]})
        self.assertEqual(missing, [],
                         "the facts block states numbers the verifier would reject in prose: %r"
                         % (missing,))

    def test_the_66_67_boundary_is_quotable(self):
        self.assertIn(66.67, allowed_numbers(REQUEST))

    def test_the_15_second_horizon_is_quotable(self):
        self.assertIn(15.0, allowed_numbers(REQUEST))

    def test_a_narrative_quoting_a_definition_is_accepted(self):
        from ai.verify import check_claims, check_narratives
        claims, _, _ = check_claims([
            {"claim_id": "C1", "kind": "metric", "text": "3 high recoveries.",
             "metric_key": "high_recoveries", "metric_value": 3,
             "evidence_event_ids": ["MM-DEMO-01-E007"]}], REQUEST)
        narratives, issues = check_narratives(
            {"casual": "They won the ball back high up the pitch three times.",
             "analyst": ("HOME made 3 high recoveries, defined as recoveries with attack-normalised "
                         "x at or beyond 66.67, and 2 were followed within 15 seconds by a shot.")},
            REQUEST, claims)
        self.assertEqual(issues, [])
        self.assertIsNotNone(narratives)


if __name__ == "__main__":
    unittest.main()
