"""Overlay, A2A card and storyline policy.

These are the three surfaces a broadcast or an outside agent consumes, so the tests focus on
the honesty properties: an unverified card may not be overlaid, a fallback may not be
presented as live, and no graphic may cite an event the insight did not.
"""
import copy
import json
import unittest
from pathlib import Path

from ai.a2a import CARD_PATH, agent_card, validate_card
from ai.overlay import OVERLAY_SCHEMA, LOWER_THIRD_MS, overlay_payload, validate_payload
from ai.storyline import Storyline, review

ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = json.loads((ROOT / "contracts/examples/analysis_result.json").read_text(encoding="utf-8"))


def fallback_insight():
    return copy.deepcopy(EXAMPLE["insight"])


def live_insight():
    insight = fallback_insight()
    insight["verification"] = {"status": "passed", "method": "agent_and_code",
                               "rejected_claims": ["C4"]}
    insight["generation"] = {"mode": "live_model", "provider": "test", "model": "test-model"}
    return insight


class OverlayTests(unittest.TestCase):
    def test_payload_is_timed_and_valid(self):
        insight = fallback_insight()
        payload = overlay_payload(insight, generated_at_ms=1234)
        self.assertEqual(payload["schema"], OVERLAY_SCHEMA)
        self.assertTrue(payload["synthetic"])
        self.assertEqual(validate_payload(payload, insight), [])
        self.assertTrue(payload["graphics"])
        kinds = {g["kind"] for g in payload["graphics"]}
        self.assertEqual(kinds, {"lower_third", "stat_line", "evidence_pin"})

    def test_graphics_never_start_before_the_window_or_end_before_they_start(self):
        insight = fallback_insight()
        payload = overlay_payload(insight)
        start_ms = payload["window"]["start_sec"] * 1000
        for graphic in payload["graphics"]:
            self.assertGreaterEqual(graphic["in_ms"], start_ms)
            self.assertLessEqual(graphic["in_ms"], graphic["out_ms"])
        first = [g for g in payload["graphics"] if g["kind"] == "lower_third"][0]
        self.assertEqual(first["in_ms"], start_ms)
        self.assertEqual(first["out_ms"] - first["in_ms"], LOWER_THIRD_MS)

    def test_an_unverified_insight_cannot_be_overlaid(self):
        insight = fallback_insight()
        insight["verification"]["status"] = "rejected"
        with self.assertRaises(ValueError):
            overlay_payload(insight)

    def test_a_live_card_without_agent_and_code_cannot_be_overlaid(self):
        insight = live_insight()
        insight["verification"]["method"] = "code_only"
        with self.assertRaises(ValueError):
            overlay_payload(insight)

    def test_every_graphic_carries_the_real_source_mode(self):
        payload = overlay_payload(live_insight())
        for graphic in payload["graphics"]:
            self.assertEqual(graphic["source"]["mode"], "live_model")
            self.assertEqual(graphic["source"]["verification"], "agent_and_code")

    def test_a_fallback_is_labelled_as_such_on_every_graphic(self):
        payload = overlay_payload(fallback_insight())
        for graphic in payload["graphics"]:
            self.assertEqual(graphic["source"]["mode"], "rule_fallback")

    def test_validate_catches_an_event_the_insight_never_cited(self):
        insight = fallback_insight()
        payload = overlay_payload(insight)
        payload["graphics"][-1]["evidence_event_ids"] = ["MM-DEMO-01-E999"]
        problems = validate_payload(payload, insight)
        self.assertTrue(any("cites an event the insight does not" in p for p in problems))

    def test_validate_catches_a_missing_source_label(self):
        payload = overlay_payload(fallback_insight())
        payload["graphics"][0].pop("source")
        self.assertTrue(any("no source label" in p for p in validate_payload(payload)))

    def test_metric_values_are_copied_not_recomputed(self):
        insight = fallback_insight()
        payload = overlay_payload(insight)
        stats = {g["metric_key"]: g["metric_value"] for g in payload["graphics"]
                 if g["kind"] == "stat_line"}
        claims = {c["metric_key"]: c["metric_value"] for c in insight["claims"]
                  if c["kind"] == "metric"}
        for key, value in claims.items():
            self.assertEqual(stats.get(key), value)

    def test_missing_window_is_refused(self):
        insight = fallback_insight()
        insight.pop("window")
        with self.assertRaises(ValueError):
            overlay_payload(insight)


class OverlayAccessibilityTests(unittest.TestCase):
    """An overlay a screen reader cannot describe is an overlay half the audience cannot use.

    This does not make the product accessible on its own — that needs a real audio UI and blind
    testers, which we do not have. It does mean the payload is not silent.
    """

    def test_every_text_graphic_has_spoken_text(self):
        payload = overlay_payload(fallback_insight())
        for graphic in payload["graphics"]:
            if graphic["kind"] in ("lower_third", "stat_line"):
                self.assertTrue(graphic["speech"].strip(), graphic["id"])

    def test_the_payload_carries_an_ordered_speech_script(self):
        payload = overlay_payload(fallback_insight())
        script = payload["speech_script"]
        self.assertTrue(script)
        times = [row["in_ms"] for row in script]
        self.assertEqual(times, sorted(times))
        for row in script:
            self.assertTrue(row["text"].strip())

    def test_the_spoken_title_uses_the_casual_narrative(self):
        insight = fallback_insight()
        payload = overlay_payload(insight)
        title = [g for g in payload["graphics"] if g["kind"] == "lower_third"][0]
        self.assertEqual(title["speech"], insight["narratives"]["casual"].strip())

    def test_a_card_without_narratives_still_says_something(self):
        insight = fallback_insight()
        insight["narratives"] = {"casual": "", "analyst": ""}
        payload = overlay_payload(insight)
        title = [g for g in payload["graphics"] if g["kind"] == "lower_third"][0]
        self.assertTrue(title["speech"].strip())
        self.assertIn("high recoveries", title["speech"])

    def test_a_stat_line_speaks_its_own_claim(self):
        insight = fallback_insight()
        payload = overlay_payload(insight)
        stats = [g for g in payload["graphics"] if g["kind"] == "stat_line"]
        self.assertTrue(stats)
        for graphic in stats:
            self.assertIn(str(graphic["metric_value"]), graphic["speech"]
                          .replace("one", "1").replace("two", "2").replace("three", "3")
                          .replace("no", "0"))

    def test_validation_refuses_a_silent_graphic(self):
        payload = overlay_payload(fallback_insight())
        title = [g for g in payload["graphics"] if g["kind"] == "lower_third"][0]
        title["speech"] = "   "
        self.assertTrue(any("no spoken text" in p for p in validate_payload(payload)))

    def test_validation_refuses_a_payload_with_no_script(self):
        payload = overlay_payload(fallback_insight())
        payload["speech_script"] = []
        self.assertTrue(any("speech_script" in p for p in validate_payload(payload)))


class AgentCardTests(unittest.TestCase):
    def test_card_is_structurally_valid(self):
        card = agent_card()
        self.assertEqual(validate_card(card), [])
        self.assertEqual(CARD_PATH, "/.well-known/agent-card.json")

    def test_card_does_not_claim_streaming_it_does_not_do(self):
        card = agent_card()
        self.assertFalse(card["capabilities"]["streaming"])

    def test_every_skill_matches_a_real_mcp_tool(self):
        from ai import mcp_server
        card = agent_card()
        tool_names = {tool.name for tool in __import__("asyncio").run(
            mcp_server.server.list_tools())}
        for skill in card["skills"]:
            self.assertIn(skill["id"], tool_names,
                          "agent card advertises a skill with no matching tool")

    def test_card_reports_model_readiness_truthfully(self):
        self.assertFalse(agent_card(model_ready=False)["x-matchmind"]["modelReady"])
        self.assertTrue(agent_card(model_ready=True)["x-matchmind"]["modelReady"])

    def test_card_states_its_own_limits(self):
        limits = agent_card()["x-matchmind"]["honestLimits"]
        self.assertTrue(limits)
        self.assertTrue(any("rule_fallback" in line for line in limits))


class StorylineTests(unittest.TestCase):
    def card(self, insight_id, start, end, kind="high_press", team="HOME", recoveries=3):
        return {"insight_id": insight_id, "match_id": "MM-DEMO-01", "type": kind,
                "team_id": team, "window": {"start_sec": start, "end_sec": end},
                "claims": [{"claim_id": "C1", "kind": "metric",
                            "metric_key": "high_recoveries", "metric_value": recoveries}]}

    def test_first_card_is_admitted_and_sequenced(self):
        storyline = Storyline()
        admit, decision = storyline.consider(self.card("INS-1", 1500, 1650))
        self.assertTrue(admit)
        self.assertEqual(decision["sequence"], 1)
        self.assertIsNone(decision["previous_insight_id"])

    def test_an_identical_window_is_refused_as_a_duplicate(self):
        storyline = Storyline()
        storyline.consider(self.card("INS-1", 1500, 1650))
        admit, decision = storyline.consider(self.card("INS-1", 1500, 1650))
        self.assertFalse(admit)
        self.assertEqual(decision["reason"], "DUPLICATE_WINDOW")

    def test_overlapping_windows_are_refused_even_when_their_ends_are_far_apart(self):
        """End-to-end spacing would let 1500-1650 and 1600-1700 both air: they differ by 50s
        at the end but describe the same spell of play twice."""
        storyline = Storyline(min_interval_sec=45)
        storyline.consider(self.card("INS-1", 1500, 1650))
        admit, decision = storyline.consider(self.card("INS-2", 1600, 1700))
        self.assertFalse(admit)
        self.assertEqual(decision["reason"], "TOO_SOON")
        self.assertEqual(decision["previous_insight_id"], "INS-1")
        self.assertEqual(decision["previous_window_end_sec"], 1650)
        self.assertEqual(decision["this_window_start_sec"], 1600)

    def test_a_later_card_is_admitted_with_continuity(self):
        storyline = Storyline(min_interval_sec=45)
        storyline.consider(self.card("INS-1", 1500, 1650, recoveries=3))
        admit, decision = storyline.consider(self.card("INS-3", 1700, 1780, recoveries=4))
        self.assertTrue(admit)
        self.assertEqual(decision["previous_insight_id"], "INS-1")
        self.assertTrue(decision["continuity"]["is_repeat"])
        self.assertEqual(decision["continuity"]["changed_metrics_since_previous"],
                         [{"metric_key": "high_recoveries", "from": 3, "to": 4}])

    def test_a_new_pattern_is_marked_as_first_occurrence(self):
        storyline = Storyline(min_interval_sec=0)
        storyline.consider(self.card("INS-1", 1500, 1650))
        admit, decision = storyline.consider(
            self.card("INS-2", 1700, 1780, kind="fast_break"))
        self.assertTrue(admit)
        self.assertFalse(decision["continuity"]["is_repeat"])
        self.assertIn("First occurrence", decision["continuity"]["note"])

    def test_the_hard_cap_stops_a_flood(self):
        storyline = Storyline(min_interval_sec=0, max_cards=2)
        storyline.consider(self.card("INS-1", 1500, 1600))
        storyline.consider(self.card("INS-2", 1610, 1650))
        admit, decision = storyline.consider(self.card("INS-3", 1660, 1700))
        self.assertFalse(admit)
        self.assertEqual(decision["reason"], "RATE_CAP")

    def test_review_reports_admissions_and_refusals(self):
        cards = [self.card("INS-1", 1500, 1650), self.card("INS-1", 1500, 1650),
                 self.card("INS-3", 1760, 1800)]
        report = review(cards, min_interval_sec=45)
        self.assertEqual(report["considered"], 3)
        self.assertEqual(report["admitted"], 2)
        self.assertEqual(report["refused"], 1)


if __name__ == "__main__":
    unittest.main()
