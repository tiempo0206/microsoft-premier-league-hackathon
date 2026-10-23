"""Token accounting: an estimate, clearly labelled, with cache hits counted as free.

The product claims it runs for cents. That claim needs a number behind it, and the number must
not be dressed up as a bill.
"""
import unittest

from ai.usage import PRICES_PER_MILLION, UsageLedger, describe


class LedgerTests(unittest.TestCase):
    def test_usage_accumulates_across_calls(self):
        ledger = UsageLedger()
        ledger.add({"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120},
                   "deepseek-flash")
        ledger.add({"prompt_tokens": 50, "completion_tokens": 10, "total_tokens": 60},
                   "deepseek-flash")
        self.assertEqual(ledger.prompt_tokens, 150)
        self.assertEqual(ledger.completion_tokens, 30)
        self.assertEqual(ledger.calls_billed, 2)

    def test_a_cache_hit_costs_nothing(self):
        ledger = UsageLedger()
        ledger.add(None, cached=True)
        ledger.add(None, cached=True)
        self.assertEqual(ledger.calls_cached, 2)
        self.assertEqual(ledger.estimate_usd(), 0.0)

    def test_an_estimate_uses_the_published_rate(self):
        ledger = UsageLedger()
        ledger.add({"prompt_tokens": 1_000_000, "completion_tokens": 1_000_000},
                   "deepseek-flash")
        off_peak = ledger.estimate_usd(peak=False)
        peak = ledger.estimate_usd(peak=True)
        rate = PRICES_PER_MILLION["deepseek-flash"]
        self.assertAlmostEqual(off_peak, rate["input"] + rate["output"], places=6)
        self.assertAlmostEqual(peak, off_peak * 2, places=6)
        self.assertGreater(peak, off_peak, "peak must never look cheaper than off-peak")

    def test_a_realistic_analysis_costs_a_fraction_of_a_cent(self):
        ledger = UsageLedger()
        # Four calls of roughly this size is what one three-agent pass looks like.
        for _ in range(4):
            ledger.add({"prompt_tokens": 1200, "completion_tokens": 250}, "deepseek-flash")
        estimate = ledger.estimate_usd()
        self.assertIsNotNone(estimate)
        self.assertLess(estimate, 0.01, "a card should cost well under a cent at flash rates")

    def test_an_unknown_model_yields_no_estimate_rather_than_a_wrong_one(self):
        ledger = UsageLedger()
        ledger.add({"prompt_tokens": 10, "completion_tokens": 5}, "mystery-model")
        self.assertIsNone(ledger.estimate_usd())

    def test_missing_usage_blocks_the_estimate(self):
        ledger = UsageLedger()
        ledger.add(None, "deepseek-flash")
        self.assertEqual(ledger.unknown_usage_calls, 1)
        self.assertIsNone(ledger.estimate_usd(),
                          "a partial total would understate the cost, so report nothing")

    def test_the_dict_carries_the_basis_of_the_estimate(self):
        ledger = UsageLedger()
        ledger.add({"prompt_tokens": 100, "completion_tokens": 20}, "deepseek-flash")
        data = ledger.as_dict()
        self.assertIn("estimate", data["estimate_basis"])
        self.assertIn("not a bill", data["estimate_basis"])
        self.assertEqual(data["models"], ["deepseek-flash"])

    def test_describe_is_honest_about_what_it_cannot_price(self):
        ledger = UsageLedger()
        ledger.add({"prompt_tokens": 10, "completion_tokens": 5}, "mystery-model")
        text = describe(ledger)
        self.assertIn("not estimated", text)

    def test_describe_mentions_cache_hits(self):
        ledger = UsageLedger()
        ledger.add(None, cached=True)
        self.assertIn("served from cache", describe(ledger))

    def test_an_empty_ledger_says_nothing(self):
        self.assertEqual(describe(UsageLedger()), "")


class TraceIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_a_live_card_records_its_token_usage_in_a_trace(self):
        import json
        from pathlib import Path

        import httpx

        from ai.config import ModelConfig
        from ai.provider import ChatCompletionsProvider
        from ai.service import analyze

        root = Path(__file__).resolve().parents[2]
        request = json.loads((root / "contracts/examples/analysis_request.json")
                             .read_text(encoding="utf-8"))
        claims = {"claims": [
            {"claim_id": "C1", "kind": "metric", "text": "3 high recoveries.",
             "metric_key": "high_recoveries", "metric_value": 3,
             "evidence_event_ids": ["MM-DEMO-01-E007"]},
            {"claim_id": "C2", "kind": "interpretation",
             "text": "The side kept recovering the ball high.",
             "metric_key": None, "metric_value": None,
             "evidence_event_ids": ["MM-DEMO-01-E013"]}]}
        narratives = {"casual": "The home side won the ball high.",
                      "analyst": "Three high recoveries; two produced a shot inside 15 seconds."}
        audit = {"approved": True, "rejected_claims": [], "narrative_problems": [], "issues": []}
        bodies = [claims, narratives, audit]

        def handler(http_request):
            payload = bodies.pop(0) if bodies else audit
            return httpx.Response(200, json={
                "model": "deepseek-flash",
                "choices": [{"message": {"role": "assistant",
                                         "content": json.dumps(payload)}}],
                "usage": {"prompt_tokens": 900, "completion_tokens": 120,
                          "total_tokens": 1020}})

        config = ModelConfig(provider="test", base_url="https://example.invalid",
                             model="deepseek-flash", api_key="sk-test", timeout=10,
                             orchestrator="direct")
        result = await analyze(request, config=config,
                              provider=ChatCompletionsProvider(
                                  config, transport=httpx.MockTransport(handler),
                                  use_cache=False))
        notes = " ".join(t.get("note", "") for t in result["traces"])
        self.assertIn("token usage", notes)
        self.assertIn("estimated", notes)
        self.assertIn("$", notes)


if __name__ == "__main__":
    unittest.main()
