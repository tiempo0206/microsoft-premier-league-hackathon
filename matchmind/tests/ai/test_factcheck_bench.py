"""Pins the verifier's measured catch rate and false-alarm rate.

The bench is hand-built, not a corpus, so its value is regression protection: if a future
change makes the verifier stricter it will show up as a false alarm here, and if it gets
looser it will show up as a missed corruption. Both directions have bitten this project
already (see docs/handoff/ai.md section 2b).
"""
import unittest

from evaluation import factcheck_bench


class FactcheckBenchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.corruptions, cls.clean = factcheck_bench.evaluate()
        cls.summary = factcheck_bench.report(cls.corruptions, cls.clean)

    def test_every_required_corruption_is_caught(self):
        missed = [g["category"] for g in self.summary["gaps"]]
        self.assertEqual(missed, [], "the verifier stopped catching: " + ", ".join(missed))
        self.assertEqual(self.summary["catch_rate"], 100.0)

    def test_no_clean_explanation_is_rejected(self):
        self.assertEqual(self.summary["false_alarm_rate"], 0.0,
                         "a correct explanation was rejected: %r"
                         % (self.summary["false_alarms"],))

    def test_the_bench_is_wide_enough_to_mean_something(self):
        self.assertGreaterEqual(self.summary["corruptions_required"], 21)
        self.assertGreaterEqual(self.summary["clean_total"], 4)

    def test_language_mismatch_is_one_of_the_covered_classes(self):
        categories = {r["category"] for r in self.corruptions}
        self.assertIn("wrong_language_english_for_chinese_request", categories)
        self.assertIn("wrong_language_chinese_for_english_request", categories)

    def test_evidence_of_the_wrong_type_is_one_of_the_covered_classes(self):
        categories = {r["category"] for r in self.corruptions}
        self.assertIn("recovery_claim_citing_only_a_shot", categories)
        self.assertIn("shots_claim_citing_only_passes", categories)

    def test_a_zero_metric_may_cite_any_event(self):
        """Zero has no event of its own type to cite, so the evidence-type rule must exempt it.
        Without the exemption a correct "took no shots" card was rejected."""
        from ai.verify import check_claims
        import copy
        import json
        from pathlib import Path
        root = Path(__file__).resolve().parents[2]
        request = json.loads((root / "contracts/examples/analysis_request.json")
                             .read_text(encoding="utf-8"))
        claim = {"claim_id": "C1", "kind": "metric",
                 "text": "AWAY took no shots in this window.",
                 "metric_key": "away_shots", "metric_value": 0,
                 "evidence_event_ids": ["MM-DEMO-01-E003"]}
        approved, rejected, issues = check_claims([claim], copy.deepcopy(request))
        self.assertEqual(rejected, [], issues)

    def test_quantifier_overreach_is_documented_as_an_auditor_job(self):
        """The regex layer cannot tell "three of three" from "two of three". That is why
        the auditor agent exists, and the bench must keep saying so rather than quietly
        counting it as a pass."""
        quantifier = [r for r in self.corruptions if r["category"] == "quantifier_overreach"]
        self.assertEqual(len(quantifier), 1)
        self.assertFalse(quantifier[0]["must_be_caught"])

    def test_chinese_and_zero_written_in_words_both_pass(self):
        clean = {c["category"]: c for c in self.clean}
        self.assertTrue(clean["clean_chinese"]["ok"])
        self.assertTrue(clean["clean_zero_written_as_words"]["ok"])


if __name__ == "__main__":
    unittest.main()
