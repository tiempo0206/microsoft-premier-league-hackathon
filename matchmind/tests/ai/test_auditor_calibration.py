"""Pins the auditor calibration corpus, not the auditor's score.

The score needs real calls, so it cannot live in a unit test. What can be pinned is the thing that
makes the score mean anything: **every rigged card in the corpus must pass the deterministic gate
unchanged**. If a future change to `ai/verify.py` starts catching one of them, this test fails and
the corpus has to be re-drawn — because a case the code gate already blocks is no longer evidence
about the auditor, and quietly counting it would inflate the auditor's apparent value.

The same test is what documents the gap: the ten cases below are all wrong, and the code accepts all
ten. That is the honest statement of why a second agent exists.
"""
import unittest

from evaluation import auditor_calibration as calibration


class CorpusShapeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.request = calibration.build_request()
        cls.plan = calibration.plan(cls.request)

    def test_every_case_is_usable_as_an_auditor_test(self):
        unusable = [row["label"] for row in self.plan["rows"] if not row["is_an_auditor_test"]]
        self.assertEqual(unusable, [],
                         "the code gate now blocks these, so they no longer test the auditor: "
                         + ", ".join(unusable))

    def test_the_code_gate_is_blind_to_every_rigged_card(self):
        for case in calibration.BAD_CASES:
            gated = calibration.gate(case, self.request)
            self.assertEqual(gated["rejected"], [], case["label"])
            self.assertIsNotNone(gated["narratives"], case["label"])
            self.assertFalse(calibration.code_gate_caught(case, gated), case["label"])

    def test_every_honest_card_clears_the_gate(self):
        for case in calibration.GOOD_CASES:
            gated = calibration.gate(case, self.request)
            self.assertEqual(gated["rejected"], [], case["label"])
            self.assertIsNotNone(gated["narratives"], case["label"])
            self.assertEqual(len(gated["approved_claims"]), len(case["claims"]), case["label"])

    def test_each_rigged_card_names_the_claim_it_rigged(self):
        for case in calibration.BAD_CASES:
            target = case["target"]
            if target == "narratives":
                continue
            self.assertIn(target, [c["claim_id"] for c in case["claims"]], case["label"])

    def test_the_rigged_claim_is_the_one_the_code_gate_cannot_see(self):
        """The planted claim must not trip the forbidden-phrase list or invent a number.

        Otherwise the case would be mislabelled: it would look like an auditor test while the
        regex layer was already covering it.
        """
        from ai.verify import stray_numbers, unsupported_phrases
        for case in calibration.BAD_CASES:
            if case["target"] == "narratives":
                texts = list(case["narratives"].values())
            else:
                texts = [c["text"] for c in case["claims"] if c["claim_id"] == case["target"]]
            for text in texts:
                self.assertEqual(unsupported_phrases(text), [], (case["label"], text))
                self.assertEqual(list(stray_numbers(text, self.request)), [],
                                 (case["label"], text))

    def test_labels_are_unique_and_the_taxonomy_is_closed(self):
        labels = [case["label"] for case in calibration.GOOD_CASES + calibration.BAD_CASES]
        self.assertEqual(len(labels), len(set(labels)))
        flaws = {case["flaw"] for case in calibration.BAD_CASES}
        self.assertLessEqual(flaws, {"contradicts_data", "unsupported_scope",
                                     "unsupported_mechanism", "narrative"})

    def test_the_corpus_covers_both_directions(self):
        self.assertGreaterEqual(len(calibration.GOOD_CASES), 3)
        self.assertGreaterEqual(len(calibration.BAD_CASES), 10)
        self.assertEqual(self.plan["by_kind"], {"accepted": len(calibration.GOOD_CASES),
                                               "rejected": len(calibration.BAD_CASES)})

    def test_the_plan_needs_no_model(self):
        """--plan must work with no key configured, or the corpus cannot be reviewed offline."""
        self.assertIn("rows", calibration.plan(self.request))
        self.assertTrue(all("code_gate_blocked_whole_card" in row
                            for row in calibration.plan(self.request)["rows"]))


class ScoringTests(unittest.TestCase):
    """A model that rejects everything must not be able to look good."""

    def entry(self, expect, approved, caught=None, named=None):
        run = {"run": 0, "approved": approved}
        if caught is not None:
            run["caught"] = caught
        if named is not None:
            run["named_target"] = named
        return {"label": "x", "expect": expect, "flaw": "contradicts_data", "target": "C2",
                "runs": [run]}

    def test_rejecting_everything_scores_zero_on_the_honest_half(self):
        results = [self.entry("accepted", False) for _ in range(3)]
        results += [self.entry("rejected", False, caught=True, named=True) for _ in range(3)]
        summary = calibration.summarise(results)
        self.assertEqual(summary["honest_cards"]["false_alarm_rate"], 100.0)
        self.assertEqual(summary["overreach_cards"]["miss_rate"], 0.0)
        self.assertEqual(summary["discrimination"]["correct_decisions"], 50.0)

    def test_approving_everything_scores_zero_on_the_rigged_half(self):
        results = [self.entry("accepted", True) for _ in range(3)]
        results += [self.entry("rejected", True, caught=False, named=False) for _ in range(3)]
        summary = calibration.summarise(results)
        self.assertEqual(summary["honest_cards"]["false_alarm_rate"], 0.0)
        self.assertEqual(summary["overreach_cards"]["miss_rate"], 100.0)
        self.assertEqual(summary["discrimination"]["correct_decisions"], 50.0)

    def test_a_catch_for_the_wrong_reason_is_not_a_targeted_catch(self):
        summary = calibration.summarise([self.entry("rejected", False, caught=True, named=False)])
        self.assertEqual(summary["overreach_cards"]["miss_rate"], 0.0)
        self.assertEqual(summary["overreach_cards"]["miss_rate_naming_the_planted_claim"], 100.0)

    def test_errors_are_not_counted_as_decisions(self):
        entry = {"label": "x", "expect": "rejected", "flaw": "narrative", "target": "narratives",
                 "runs": [{"run": 0, "error": "ProviderTimeout"},
                          {"run": 1, "approved": False, "caught": True, "named_target": True}]}
        summary = calibration.summarise([entry])
        self.assertEqual(summary["overreach_cards"]["runs"], 1)
        self.assertEqual(summary["overreach_cards"]["miss_rate"], 0.0)

    def test_by_flaw_groups_the_rigged_cards(self):
        results = [self.entry("rejected", False, caught=True, named=True),
                   self.entry("rejected", True, caught=False, named=False)]
        summary = calibration.summarise(results)
        self.assertEqual(summary["overreach_cards"]["by_flaw"]["contradicts_data"]["cases"], 2)
        self.assertEqual(summary["overreach_cards"]["by_flaw"]["contradicts_data"]["caught_rate"],
                         50.0)

    def test_skipped_cases_are_listed_not_hidden(self):
        results = [{"label": "gone", "expect": "rejected", "flaw": "narrative",
                    "target": "narratives", "runs": [],
                    "skipped": "the code gate rejected this case"}]
        summary = calibration.summarise(results)
        self.assertEqual(summary["skipped"], ["gone"])
        self.assertEqual(summary["overreach_cards"]["runs"], 0)


if __name__ == "__main__":
    unittest.main()
