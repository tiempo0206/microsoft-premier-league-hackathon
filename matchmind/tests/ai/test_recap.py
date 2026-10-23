"""Recap role: deterministic, cutoff-respecting, and able to say what a moment card cannot.

The shipped fixture makes the point concrete: no single 150-second moment window contains
both the 1640 recovery and the 1680 goal, so no moment card can mention the goal. A recap
covers the whole prefix and reports it. That is why this role exists and why it is not just
a longer card.
"""
import unittest

from ai.recap import (RECAP_SCHEMA, build_recap, recap_facts, recap_from_insights,
                      recap_from_insights_issues, recap_narrative, recap_series_issues,
                      validate_recap)


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


class SeriesConsistencyTests(unittest.TestCase):
    """Each recap can be perfect and the series still contradict itself."""

    def series(self):
        return [build_recap("MM-DEMO-01", 1500, 1550),
                build_recap("MM-DEMO-01", 1500, 1600),
                build_recap("MM-DEMO-01", 1500, 1650),
                build_recap("MM-DEMO-01", 1500, 1700),
                build_recap("MM-DEMO-01", 1500, 1800)]

    def test_an_honest_series_is_consistent(self):
        self.assertEqual(recap_series_issues(self.series()), [])

    def test_input_order_does_not_matter(self):
        series = self.series()
        shuffled = [series[3], series[0], series[4], series[2], series[1]]
        self.assertEqual(recap_series_issues(shuffled), [])

    def test_one_recap_alone_has_nothing_to_contradict(self):
        self.assertEqual(recap_series_issues([build_recap("MM-DEMO-01", 1500, 1650)]), [])

    def test_a_counter_going_backwards_is_caught(self):
        # The realistic corruption: the 1700 recap reads only 1650-1700 instead of the whole
        # prefix, so its cumulative possession is smaller than the 1600 recap's.
        series = self.series()
        self.assertEqual(series[3]["facts"]["possession_seconds"]["HOME"], 70)
        series[3]["facts"]["possession_seconds"]["HOME"] = 5
        problems = recap_series_issues(series)
        self.assertTrue(any("possession_seconds.HOME went down" in p for p in problems), problems)

    def test_a_counter_that_only_grows_is_not_flagged(self):
        series = self.series()
        series[3]["facts"]["possession_seconds"]["HOME"] = 36
        self.assertEqual(recap_series_issues(series), [])

    def test_a_score_going_backwards_is_caught(self):
        series = self.series()
        series[4]["facts"]["score_after"]["HOME"] = 0
        self.assertTrue(any("score_after.HOME went down" in p
                            for p in recap_series_issues(series)))

    def test_the_same_goal_credited_to_two_players_is_caught(self):
        series = self.series()
        self.assertEqual(len(series[4]["facts"]["goals"]), 1)
        series[4]["facts"]["goals"][0] = dict(series[4]["facts"]["goals"][0],
                                             player_id="H99")
        series[4]["facts"]["goals"][0]["player_id"] = "H99"
        problems = recap_series_issues(series)
        self.assertTrue(any("credited to" in p for p in problems), problems)

    def test_two_recaps_of_the_same_window_must_agree(self):
        first = build_recap("MM-DEMO-01", 1500, 1650)
        second = build_recap("MM-DEMO-01", 1500, 1650)
        second["facts"]["shots"]["HOME"] += 1
        problems = recap_series_issues([first, second])
        self.assertTrue(any("same window but disagree on shots" in p for p in problems), problems)

    def test_same_cutoff_different_start_is_caught(self):
        first = build_recap("MM-DEMO-01", 1500, 1650)
        second = build_recap("MM-DEMO-01", 1550, 1650)
        problems = recap_series_issues([first, second])
        self.assertTrue(any("share cutoff 1650 but start at" in p for p in problems), problems)

    def test_mixed_matches_are_caught(self):
        series = self.series()
        series[2]["match_id"] = "MM-OTHER"
        self.assertTrue(any("mixes match ids" in p for p in recap_series_issues(series)))

    def test_a_broken_payload_is_reported_once_not_fatal(self):
        series = self.series()
        series[1]["narrative"]["analyst"] = ""
        problems = recap_series_issues(series)
        self.assertTrue(any("both audiences" in p for p in problems))
        self.assertEqual(recap_series_issues([{}, {"schema": "x"}]) != [], True)
        self.assertEqual(recap_series_issues("not a list"), ["recap series must be a list"])

    def test_a_single_goal_stays_credited_the_same_way_across_the_series(self):
        series = self.series()
        credited = {(g["event_id"], g["team_id"], g["player_id"])
                    for recap in series for g in recap["facts"]["goals"]}
        self.assertEqual(credited, {("MM-DEMO-01-E023", "HOME", "H01")})


class CardBasedRecapConsistencyTests(unittest.TestCase):
    def insight(self, insight_id, start, end, match_id="MM-DEMO-01"):
        return {"insight_id": insight_id, "match_id": match_id, "type": "high_press",
                "window": {"start_sec": start, "end_sec": end},
                "claims": [{"claim_id": "C1", "kind": "metric",
                            "metric_key": "high_recoveries", "metric_value": 3}],
                "generation": {"mode": "rule_fallback"},
                "evidence_event_ids": ["MM-DEMO-01-E007"]}

    def test_a_clean_card_recap_has_no_problems(self):
        cards = [self.insight("INS-1", 1500, 1650), self.insight("INS-2", 1650, 1800)]
        recap = recap_from_insights(cards)
        self.assertEqual(recap_from_insights_issues(recap, cards), [])

    def test_overlapping_cards_are_caught(self):
        cards = [self.insight("INS-1", 1500, 1650), self.insight("INS-2", 1600, 1700)]
        recap = recap_from_insights(cards)
        problems = recap_from_insights_issues(recap, cards)
        self.assertTrue(any("starts at 1600, before card" in p for p in problems), problems)

    def test_cards_from_two_matches_are_caught(self):
        cards = [self.insight("INS-1", 1500, 1650), self.insight("INS-2", 1700, 1780, "MM-OTHER")]
        recap = recap_from_insights(cards)
        self.assertTrue(any("mixes match ids" in p
                            for p in recap_from_insights_issues(recap, cards)))

    def test_a_card_past_the_cutoff_is_caught(self):
        cards = [self.insight("INS-1", 1500, 1650), self.insight("INS-2", 1700, 1780)]
        recap = recap_from_insights(cards)
        recap["cutoff_sec"] = 1700
        problems = recap_from_insights_issues(recap, cards)
        self.assertTrue(any("past the recap cutoff" in p for p in problems), problems)

    def test_a_dropped_card_is_caught(self):
        cards = [self.insight("INS-1", 1500, 1650), self.insight("INS-2", 1700, 1780)]
        recap = recap_from_insights(cards)
        recap["cards"] = recap["cards"][:1]
        self.assertTrue(any("left out aired cards" in p
                            for p in recap_from_insights_issues(recap, cards)))

    def test_no_cards_is_reported_not_crashed(self):
        self.assertEqual(recap_from_insights_issues({"cutoff_sec": 1}, []), ["no cards"])


if __name__ == "__main__":
    unittest.main()
