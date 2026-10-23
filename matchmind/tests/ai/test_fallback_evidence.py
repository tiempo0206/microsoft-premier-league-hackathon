"""The fallback card's evidence must cover the claims it keeps.

Role B found this defect on its own showcase data and reported it with a reproduction rather than a
patch, which is the right way round: the fallback is Role C's module. Its words:

    `ai/fallback.py::_evidence` returns at most 12 IDs. `rule_claims` separately selects
    recovery/shot IDs from every chain. A claim can therefore reference a valid input event that is
    absent from `Insight.evidence_event_ids`. The shared `check_result` correctly raises.

Measured consequence: **4 of 12 normal inputs** produced a card the shared validator refuses, on
data denser than the shipped fixture. The shipped 300-second clip cannot expose it, so the fix has
to be pinned by a fixture dense enough to have more than four chains — which is exactly what
`evaluation.dense_fixture_proposal` can build offline, with no data borrowed from Role B.
"""
import tempfile
import unittest
from pathlib import Path

from ai.fallback import card_evidence, rule_result
from ai.verify import high_press_chains
from backend.data import Catalog
from backend.inputs import analysis_input
from contracts.validation import check_result
from evaluation import dense_fixture_proposal as proposal

ROOT = Path(__file__).resolve().parents[2]


def burst_request(chain_count=6):
    """A window with `chain_count` press chains — more than the evidence cap tolerates."""
    presses = proposal.spread_presses(1500, 1800, every_sec=10 ** 6, first_at=20,
                                      burst_size=chain_count, burst_gap=20)
    events = proposal.generate(seed=11, clip_start=1500, clip_end=1800, presses=presses)
    directory = Path(tempfile.mkdtemp(prefix="dense-evidence-"))
    proposal.write(directory, events, seed=11, clip_start=1500, clip_end=1800)
    fixture = Catalog(directory).fixtures["DENSE-01"]
    return analysis_input(fixture, replay_id="R-DENSE", run_id=1, task_id="TASK-DENSE",
                          start_sec=1500, end_sec=1650)


class CardEvidenceTests(unittest.TestCase):
    def test_the_union_keeps_order_and_appends_only_what_is_missing(self):
        self.assertEqual(card_evidence(["A", "B"], []), ["A", "B"])
        claims = [{"evidence_event_ids": ["B", "C"]}, {"evidence_event_ids": ["A", "D", "C"]}]
        self.assertEqual(card_evidence(["A", "B"], claims), ["A", "B", "C", "D"])

    def test_a_card_whose_claims_fit_is_unchanged(self):
        base = ["A", "B", "C"]
        claims = [{"evidence_event_ids": ["A"]}, {"evidence_event_ids": ["B", "C"]}]
        self.assertEqual(card_evidence(base, claims), base)

    def test_a_claim_with_no_evidence_does_not_break_the_union(self):
        self.assertEqual(card_evidence(["A"], [{"evidence_event_ids": []}, {}]), ["A"])


class DenseFallbackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.request = burst_request()
        cls.result = rule_result(cls.request, reason="no_model")
        cls.insight = cls.result["insight"]

    def test_the_fixture_is_dense_enough_to_reproduce_the_defect(self):
        """Guard on the guard: if this window stops having more than four chains, the test below
        would pass for the wrong reason — the cap would never be reached."""
        chains = high_press_chains(self.request)
        self.assertGreaterEqual(len(chains), 5, "the window no longer stresses the evidence cap")
        cited = {eid for claim in self.insight["claims"]
                 for eid in claim["evidence_event_ids"]}
        self.assertGreater(len(cited), 12,
                           "the claim set no longer exceeds the twelve-id base cap")

    def test_every_retained_claim_is_covered_by_the_card_evidence(self):
        card = set(self.insight["evidence_event_ids"])
        for claim in self.insight["claims"]:
            missing = set(claim["evidence_event_ids"]) - card
            self.assertEqual(missing, set(),
                             claim["claim_id"] + " cites events the card dropped: "
                             + ", ".join(sorted(missing)))

    def test_the_shared_validator_accepts_the_card(self):
        check_result(self.request, self.result)

    def test_the_card_is_still_labelled_a_fallback(self):
        self.assertEqual(self.insight["generation"]["mode"], "rule_fallback")
        self.assertEqual(self.result["error"]["code"], "MODEL_UNAVAILABLE")

    def test_no_metric_value_was_softened_to_fit(self):
        self.assertEqual(self.insight["metrics"], self.request["metrics"])
        for claim in self.insight["claims"]:
            if claim["kind"] == "metric":
                self.assertEqual(claim["metric_value"],
                                 self.request["metrics"][claim["metric_key"]])


class ShippedFixtureFallbackTests(unittest.TestCase):
    """The fix must not rewrite the card the small fixture already produced."""

    def request(self):
        fixture = Catalog(ROOT / "data" / "extra" / "validated-demo").fixtures["MM-DEMO-01"]
        return analysis_input(fixture, replay_id="R-SHIP", run_id=1, task_id="TASK-SHIP",
                              start_sec=1500, end_sec=1650)

    def test_the_shipped_card_still_passes_the_shared_validator(self):
        request = self.request()
        check_result(request, rule_result(request, reason="no_model"))

    def test_the_shipped_card_evidence_is_not_extended(self):
        """The small fixture's card already fitted inside the cap, so the fix must leave it alone
        rather than quietly growing the payload of every existing card."""
        from ai.fallback import _evidence
        request = self.request()
        base = _evidence(request, high_press_chains(request))
        insight = rule_result(request, reason="no_model")["insight"]
        self.assertEqual(insight["evidence_event_ids"], base)
        self.assertLessEqual(len(base), 12)


if __name__ == "__main__":
    unittest.main()
