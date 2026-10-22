"""Recap role: deterministic, cutoff-respecting, and able to say what a moment card cannot.

The shipped fixture makes the point concrete: no single 150-second moment window contains
both the 1640 recovery and the 1680 goal, so no moment card can mention the goal. A recap
covers the whole prefix and reports it. That is why this role exists and why it is not just
a longer card.
"""
import unittest

from ai.recap import (RECAP_SCHEMA, build_recap, recap_facts, recap_from_insights,
                      recap_narrative, validate_recap)


class FactsTests(unittest.TestCase):
    def test_facts_are_computed_not_asserted(self):
        payload = build_recap("MM-DEMO-01", 1500, 1800)
        facts = payload["facts"]
        self.assertEqual(facts["event_count"], 30)
        self.assertEqual(facts["score_after"], {"HOME": 1, "AWAY": 0})
        self.assertEqual(facts["score_change"], {"HOME": 1, "AWAY": 0})
        self.assertEqual(len(facts["goals"]), 1)
        self.assertEqual(facts["goals"][0]["event_id"], "MM-DEMO-01-E023")
        self.assertEqual(payload["problems"], [])

    def test_a_recap_reports_the_goal_a_moment_card_cannot_see(self):
        payload = build_recap("MM-DEMO-01", 1500, 1800)
        self.assertIn("H01", payload["narrative"]["analyst"])
        self.assertIn("40 seconds later", payload["narrative"]["analyst"])

    def test_a_short_recap_must_not_read_past_its_cutoff(self):
        facts = recap_facts(
            __import__("backend.data", fromlist=["Catalog"]).Catalog(
                __import__("pathlib").Path("data/extra/validated-demo")).fixtures["MM-DEMO-01"],
            1500, 1650)
        for goal in facts["goals"]:
            self.assertLessEqual(goal["timestamp_sec"], 1650)
        self.assertEqual(facts["goals"], [], "the goal at 1681 is outside a 1650 cutoff")
        self.assertEqual(facts["score_change"], {"HOME": 0, "AWAY": 0})

    def test_outside_the_clip_is_refused(self):
        with self.assertRaises(ValueError):
            build_recap("MM-DEMO-01", 1400, 1800)
        with self.assertRaises(ValueError):
            build_recap("MM-DEMO-01", 1500, 9999)

    def test_reversed_or_empty_window_is_refused(self):
        with self.assertRaises(ValueError):
            build_recap("MM-DEMO-01", 1800, 1500)
        with self.assertRaises(ValueError):
            build_recap("MM-DEMO-01", 1500, 1500)

    def test_unknown_match_is_refused(self):
        with self.assertRaises(ValueError):
            build_recap("NOPE", 1500, 1800)


class NarrativeTests(unittest.TestCase):
    def test_english_narrative_has_both_audiences_and_no_causal_claim(self):
        payload = build_recap("MM-DEMO-01", 1500, 1800)
        narrative = payload["narrative"]
        self.assertTrue(narrative["casual"])
        self.assertTrue(narrative["analyst"])
        self.assertIn("not a causal explanation", narrative["analyst"])
        for banned in ("fatigue", "tired", "because", "coach"):
            self.assertNotIn(banned, narrative["analyst"].lower(), banned)

    def test_chinese_narrative_is_generated(self):
        payload = build_recap("MM-DEMO-01", 1500, 1800, language="zh")
        self.assertTrue(any("\u4e00" <= ch <= "\u9fff"
                            for ch in payload["narrative"]["analyst"]))
        self.assertEqual(payload["title"], "目前为止的比赛走势")

    def test_narrative_never_states_a_number_the_facts_do_not_hold(self):
        payload = build_recap("MM-DEMO-01", 1500, 1800)
        facts = payload["facts"]
        from ai.verify import numbers_in
        allowed = set()
        for value in (facts["seconds_covered"], facts["score_after"]["HOME"],
                      facts["score_after"]["AWAY"], facts["shots"]["HOME"],
                      facts["shots"]["AWAY"], facts["possession_seconds"]["HOME"],
                      facts["possession_seconds"]["AWAY"],
                      facts["completed_passes"]["HOME"], facts["completed_passes"]["AWAY"],
                      37, 40):
            allowed.add(float(value))
        for audience, text in payload["narrative"].items():
            stray = {n for n in numbers_in(text) if n not in allowed}
            self.assertEqual(stray, set(),
                             audience + " states numbers the facts do not hold: %r" % stray)


class PayloadTests(unittest.TestCase):
    def test_payload_is_honest_about_generation(self):
        payload = build_recap("MM-DEMO-01", 1500, 1800)
        self.assertEqual(payload["generation"]["mode"], "rule_fallback")
        self.assertIsNone(payload["generation"]["model"])
        self.assertFalse(payload["model_ready"])
        self.assertTrue(payload["synthetic"])

    def test_validator_catches_a_live_recap_without_a_model(self):
        payload = build_recap("MM-DEMO-01", 1500, 1800)
        payload["generation"] = {"mode": "live_model", "provider": "test", "model": None}
        self.assertTrue(any("must name its model" in p for p in validate_recap(payload)))

    def test_validator_catches_a_broken_cutoff(self):
        payload = build_recap("MM-DEMO-01", 1500, 1800)
        payload["cutoff_sec"] = 1700
        self.assertTrue(any("cutoff" in p for p in validate_recap(payload)))

    def test_validator_catches_a_missing_audience(self):
        payload = build_recap("MM-DEMO-01", 1500, 1800)
        payload["narrative"]["analyst"] = ""
        self.assertTrue(any("both audiences" in p for p in validate_recap(payload)))

    def test_schema_is_versioned(self):
        self.assertEqual(build_recap("MM-DEMO-01", 1500, 1800)["schema"], RECAP_SCHEMA)


class RecapFromInsightsTests(unittest.TestCase):
    def insight(self, insight_id, start, end, value, mode="rule_fallback"):
        return {"insight_id": insight_id, "match_id": "MM-DEMO-01", "type": "high_press",
                "window": {"start_sec": start, "end_sec": end},
                "claims": [{"claim_id": "C1", "kind": "metric",
                            "metric_key": "high_recoveries", "metric_value": value}],
                "generation": {"mode": mode},
                "evidence_event_ids": ["MM-DEMO-01-E007"]}

    def test_recap_of_published_cards_only_mentions_those_cards(self):
        recap = recap_from_insights([self.insight("INS-1", 1500, 1650, 3),
                                     self.insight("INS-2", 1700, 1780, 4)])
        self.assertEqual(len(recap["cards"]), 2)
        self.assertEqual(recap["window"], {"start_sec": 1500, "end_sec": 1780})
        self.assertEqual(recap["metric_history"]["high_recoveries"], [3, 4])
        self.assertEqual(recap["source_modes"], ["rule_fallback"])

    def test_cards_are_ordered_by_window_not_input_order(self):
        recap = recap_from_insights([self.insight("INS-2", 1700, 1780, 4),
                                     self.insight("INS-1", 1500, 1650, 3)])
        self.assertEqual([c["insight_id"] for c in recap["cards"]], ["INS-1", "INS-2"])

    def test_no_cards_is_refused(self):
        with self.assertRaises(ValueError):
            recap_from_insights([])

    def test_mixed_source_modes_are_reported_not_flattened(self):
        recap = recap_from_insights([self.insight("INS-1", 1500, 1650, 3),
                                     self.insight("INS-2", 1700, 1780, 4, mode="live_model")])
        self.assertEqual(recap["source_modes"], ["live_model", "rule_fallback"])


if __name__ == "__main__":
    unittest.main()
