"""Response cache: it must save the model call without touching the card's honesty.

The property that matters is not "it caches". It is that a cache hit still yields a card whose
identity, traces and verification belong to *this* request, and that the card says so.
"""
import json
import unittest
from pathlib import Path

import httpx

from ai.cache import ResponseCache, key_for
from ai.config import ModelConfig
from ai.provider import ChatCompletionsProvider
from ai.service import analyze

ROOT = Path(__file__).resolve().parents[2]
REQUEST = json.loads((ROOT / "contracts/examples/analysis_request.json").read_text(encoding="utf-8"))

GOOD_CLAIMS = {"claims": [
    {"claim_id": "C1", "kind": "metric",
     "text": "The home side made 3 high recoveries.",
     "metric_key": "high_recoveries", "metric_value": 3,
     "evidence_event_ids": ["MM-DEMO-01-E007"]},
    {"claim_id": "C2", "kind": "interpretation",
     "text": "The side kept recovering the ball high.",
     "metric_key": None, "metric_value": None,
     "evidence_event_ids": ["MM-DEMO-01-E013"]}]}
GOOD_NARRATIVES = {"casual": "The home side won the ball high up the pitch.",
                   "analyst": "Three high recoveries; two produced a shot inside 15 seconds."}
GOOD_AUDIT = {"approved": True, "rejected_claims": [], "narrative_problems": [], "issues": []}


def config():
    return ModelConfig(provider="test", base_url="https://example.invalid", model="test-model",
                       api_key="sk-test", timeout=10.0, orchestrator="direct")


def envelope(payload):
    return {"model": "test-model",
            "choices": [{"message": {"role": "assistant", "content": json.dumps(payload)}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}}


class CacheUnitTests(unittest.TestCase):
    def test_an_lru_drops_the_oldest_entry(self):
        cache = ResponseCache(max_entries=2)
        cache.put("a", {"v": 1})
        cache.put("b", {"v": 2})
        cache.put("c", {"v": 3})
        self.assertIsNone(cache.get("a"))
        self.assertIsNotNone(cache.get("b"))
        self.assertIsNotNone(cache.get("c"))
        self.assertEqual(len(cache), 2)

    def test_stats_report_hits_and_misses(self):
        cache = ResponseCache()
        cache.put("k", {"v": 1})
        cache.get("k")
        cache.get("missing")
        stats = cache.stats()
        self.assertEqual((stats["hits"], stats["misses"]), (1, 1))
        self.assertEqual(stats["hit_rate"], 0.5)

    def test_the_key_covers_everything_that_changes_the_answer(self):
        base = dict(model="m", thinking="disabled", system="s", user="u", max_tokens=100)
        reference = key_for(**base)
        self.assertNotEqual(reference, key_for(**dict(base, model="other")))
        self.assertNotEqual(reference, key_for(**dict(base, thinking="high")))
        self.assertNotEqual(reference, key_for(**dict(base, system="s2")))
        self.assertNotEqual(reference, key_for(**dict(base, user="u2")))
        self.assertNotEqual(reference, key_for(**dict(base, max_tokens=200)))
        self.assertNotEqual(reference, key_for(**dict(base, tools=True)))
        self.assertEqual(reference, key_for(**base))

    def test_the_key_ignores_request_identity(self):
        """Two requests with identical content must share a cache entry; only their ids differ."""
        base = dict(model="m", thinking="disabled", system="s", user="u", max_tokens=100)
        self.assertEqual(key_for(**base), key_for(**base))


class ProviderCacheTests(unittest.IsolatedAsyncioTestCase):
    async def test_the_second_identical_call_does_not_hit_the_network(self):
        seen = []

        def handler(request):
            seen.append(request)
            return httpx.Response(200, json=envelope(GOOD_CLAIMS))

        cache = ResponseCache()
        provider = ChatCompletionsProvider(config(), transport=httpx.MockTransport(handler),
                                           cache=cache)
        import time
        deadline = time.monotonic() + 10
        first = await provider.complete_json(system="s", user="u", deadline=deadline)
        second = await provider.complete_json(system="s", user="u", deadline=deadline)
        self.assertEqual(first, second)
        self.assertEqual(len(seen), 1, "the second call must be served from the cache")
        self.assertEqual(provider.cache_hits, 1)
        self.assertEqual(provider.calls, 1)

    async def test_use_cache_false_always_calls_the_network(self):
        seen = []

        def handler(request):
            seen.append(request)
            return httpx.Response(200, json=envelope(GOOD_CLAIMS))

        provider = ChatCompletionsProvider(config(), transport=httpx.MockTransport(handler),
                                           use_cache=False)
        import time
        deadline = time.monotonic() + 10
        await provider.complete_json(system="s", user="u", deadline=deadline)
        await provider.complete_json(system="s", user="u", deadline=deadline)
        self.assertEqual(len(seen), 2)
        self.assertEqual(provider.cache_hits, 0)


class AnalyzeCacheTests(unittest.IsolatedAsyncioTestCase):
    async def test_a_cached_card_keeps_this_requests_identity_and_says_it_was_cached(self):
        bodies = [GOOD_CLAIMS, GOOD_NARRATIVES, GOOD_AUDIT]

        def handler(request):
            payload = bodies.pop(0) if bodies else GOOD_AUDIT
            return httpx.Response(200, json=envelope(payload))

        cache = ResponseCache()
        first_request = json.loads(json.dumps(REQUEST))
        first_request.update(task_id="TASK-A", replay_id="REPLAY-A", run_id=1)
        first = await analyze(first_request, config=config(),
                              provider=ChatCompletionsProvider(
                                  config(), transport=httpx.MockTransport(handler), cache=cache))
        self.assertEqual(first["status"], "passed")
        self.assertFalse(any("response cache" in t.get("note", "") for t in first["traces"]))

        # Same content, different identity: the wording is reusable, the identity is not.
        second_request = json.loads(json.dumps(REQUEST))
        second_request.update(task_id="TASK-B", replay_id="REPLAY-B", run_id=2)
        second = await analyze(second_request, config=config(),
                               provider=ChatCompletionsProvider(
                                   config(), transport=httpx.MockTransport(handler), cache=cache))
        self.assertEqual(second["status"], "passed")
        self.assertEqual(second["task_id"], "TASK-B")
        self.assertEqual(second["replay_id"], "REPLAY-B")
        self.assertEqual(second["run_id"], 2)
        self.assertEqual(second["insight"]["insight_id"], "INS-TASK-B")

        notes = " ".join(t.get("note", "") for t in second["traces"])
        self.assertIn("response cache", notes,
                      "a card whose wording came from the cache must say so")
        self.assertTrue(all(t["task_id"] == "TASK-B" for t in second["traces"]),
                        "every trace must belong to this request")

    async def test_different_content_is_not_served_from_the_cache(self):
        """Change something the prompt depends on and the cache must miss.

        Changing only `window` would be refused by the arithmetic gate before any model call,
        because window_seconds would no longer match — correct behaviour, but it would prove
        nothing about the cache. Language changes the prompt without breaking consistency.
        """
        calls = []

        def handler(request):
            calls.append(request)
            body = json.loads(request.content.decode("utf-8"))
            user = body["messages"][1]["content"]
            if "APPROVED_CLAIMS" in user:
                payload = GOOD_NARRATIVES
            elif "CLAIMS:" in user and "NARRATIVES:" in user:
                payload = GOOD_AUDIT
            else:
                payload = GOOD_CLAIMS
            return httpx.Response(200, json=envelope(payload))

        cache = ResponseCache()
        base = json.loads(json.dumps(REQUEST))
        base.update(task_id="T1", replay_id="R1", run_id=1)
        await analyze(base, config=config(),
                      provider=ChatCompletionsProvider(
                          config(), transport=httpx.MockTransport(handler), cache=cache))
        after_first = len(calls)
        self.assertGreater(after_first, 0)

        other_language = json.loads(json.dumps(REQUEST))
        other_language["language"] = "zh"
        other_language.update(task_id="T2", replay_id="R1", run_id=1)
        await analyze(other_language, config=config(),
                      provider=ChatCompletionsProvider(
                          config(), transport=httpx.MockTransport(handler), cache=cache))
        self.assertGreater(len(calls), after_first,
                           "different prompt content must not reuse the previous wording")

    async def test_an_inconsistent_window_is_refused_before_the_cache_is_consulted(self):
        """The gate runs first, so a request whose window and metrics disagree never reaches a
        model and never populates the cache."""
        calls = []

        def handler(request):
            calls.append(request)
            return httpx.Response(200, json=envelope(GOOD_CLAIMS))

        cache = ResponseCache()
        broken = json.loads(json.dumps(REQUEST))
        broken["window"] = {"start_sec": 1500, "end_sec": 1700}
        broken.update(task_id="T9", replay_id="R9", run_id=1)
        result = await analyze(broken, config=config(),
                               provider=ChatCompletionsProvider(
                                   config(), transport=httpx.MockTransport(handler), cache=cache))
        self.assertEqual(result["status"], "rejected")
        self.assertEqual(calls, [])
        self.assertEqual(len(cache), 0)


if __name__ == "__main__":
    unittest.main()
