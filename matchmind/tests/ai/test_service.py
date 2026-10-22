"""Role C unit tests. Every test mocks the network.

The card in roles/C_AI.md forbids a test that reaches a paid endpoint merely because the
developer's machine happens to hold a key. Nothing here constructs a real transport, and
`analyze(request)` with no arguments performs no I/O at all.
"""
import asyncio
import copy
import json
import unittest
from pathlib import Path

import httpx

from ai.config import ModelConfig
from ai.provider import ChatCompletionsProvider
from ai.service import analyze
from ai.tools import Toolbox
from ai.verify import (allowed_numbers, check_claims, check_narratives,
                       consistency_issues, numbers_in, stray_numbers)
from contracts.validation import check_result

ROOT = Path(__file__).resolve().parents[2]


def load_request():
    return json.loads((ROOT / "contracts/examples/analysis_request.json").read_text(encoding="utf-8"))


def config(**overrides):
    base = dict(provider="test", base_url="https://example.invalid", model="test-model",
                api_key="sk-not-a-real-key", timeout=12.0, thinking="disabled")
    base.update(overrides)
    return ModelConfig(**base)


def envelope(content, model="test-model"):
    return {"model": model,
            "choices": [{"message": {"role": "assistant", "content": content}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120}}


class QueueTransport:
    """Returns canned bodies in order and records how many calls happened."""

    def __init__(self, bodies):
        self.bodies = list(bodies)
        self.requests = []

    def handler(self, request):
        self.requests.append(json.loads(request.content.decode("utf-8")))
        if not self.bodies:
            raise httpx.ConnectError("unexpected extra call")
        item = self.bodies.pop(0)
        if isinstance(item, Exception):
            raise item
        return httpx.Response(200, json=envelope(json.dumps(item)))

    def build(self):
        return httpx.MockTransport(self.handler)


class FailingTransport:
    def __init__(self, side_effect):
        self.side_effect, self.count = side_effect, 0

    def handler(self, request):
        self.count += 1
        raise self.side_effect

    def build(self):
        return httpx.MockTransport(self.handler)


GOOD_CLAIMS = {
    "claims": [
        {"claim_id": "C1", "kind": "metric",
         "text": "The home side made 3 high recoveries in this window.",
         "metric_key": "high_recoveries", "metric_value": 3,
         "evidence_event_ids": ["MM-DEMO-01-E007", "MM-DEMO-01-E013", "MM-DEMO-01-E019"]},
        {"claim_id": "C2", "kind": "interpretation",
         "text": "The side kept recovering the ball high and shooting quickly.",
         "metric_key": None, "metric_value": None,
         "evidence_event_ids": ["MM-DEMO-01-E007", "MM-DEMO-01-E009"]},
    ]
}
GOOD_NARRATIVES = {"casual": "The home side kept winning the ball high up the pitch.",
                   "analyst": "Three high recoveries, two of them turned into shots inside 15 seconds."}
GOOD_AUDIT = {"approved": True, "rejected_claims": [], "narrative_problems": [], "issues": []}


def provider_for(bodies):
    transport = QueueTransport(bodies)
    return ChatCompletionsProvider(config(), transport=transport.build()), transport


class OfflineDefaultTests(unittest.IsolatedAsyncioTestCase):
    async def test_bare_analyze_never_touches_the_network(self):
        request = load_request()
        result = await analyze(request)
        self.assertEqual(result["status"], "fallback")
        self.assertEqual(result["insight"]["generation"]["mode"], "rule_fallback")
        self.assertEqual(result["insight"]["generation"]["model"], None)
        self.assertEqual(result["insight"]["verification"]["method"], "code_only")
        check_result(request, result)

    async def test_identity_is_returned_unchanged(self):
        request = load_request()
        request.update(task_id="TASK-XYZ", replay_id="REPLAY-9", run_id=7)
        result = await analyze(request)
        self.assertEqual((result["task_id"], result["replay_id"], result["run_id"]),
                         ("TASK-XYZ", "REPLAY-9", 7))
        check_result(request, result)

    async def test_unconfigured_config_is_a_labelled_fallback(self):
        request = load_request()
        result = await analyze(request, config=config(api_key=""))
        self.assertEqual(result["status"], "fallback")
        self.assertEqual(result["error"]["code"], "MODEL_UNAVAILABLE")
        self.assertFalse(result["error"]["retryable"])
        check_result(request, result)

    async def test_chinese_language_fallback(self):
        request = load_request()
        request["language"] = "zh"
        result = await analyze(request)
        insight = result["insight"]
        self.assertTrue(any("\u4e00" <= ch <= "\u9fff" for ch in insight["narratives"]["casual"]))
        check_result(request, result)


class RefusalTests(unittest.IsolatedAsyncioTestCase):
    async def test_metrics_that_contradict_events_are_rejected_not_narrated(self):
        request = load_request()
        request["metrics"]["high_recoveries"] = 8
        result = await analyze(request)
        self.assertEqual(result["status"], "rejected")
        self.assertIsNone(result["insight"])
        self.assertEqual(result["error"]["code"], "INVALID_REQUEST")
        check_result(request, result)

    async def test_shot_count_that_contradicts_events_is_rejected(self):
        request = load_request()
        request["metrics"]["home_shots"] = 9
        self.assertTrue(consistency_issues(request))
        result = await analyze(request)
        self.assertEqual(result["status"], "rejected")

    async def test_request_outside_window_is_rejected(self):
        request = load_request()
        request["events"][0]["timestamp_sec"] = 1400
        result = await analyze(request)
        self.assertEqual(result["status"], "rejected")
        self.assertEqual(result["error"]["code"], "INVALID_REQUEST")

    async def test_request_without_identity_raises_instead_of_faking_one(self):
        request = load_request()
        request.pop("task_id")
        with self.assertRaises(ValueError):
            await analyze(request)


class LivePathTests(unittest.IsolatedAsyncioTestCase):
    async def test_valid_model_output_passes_with_live_labels(self):
        request = load_request()
        provider, transport = provider_for([GOOD_CLAIMS, GOOD_NARRATIVES, GOOD_AUDIT])
        result = await analyze(request, config=config(), provider=provider)
        self.assertEqual(result["status"], "passed")
        insight = result["insight"]
        self.assertEqual(insight["generation"]["mode"], "live_model")
        self.assertEqual(insight["generation"]["model"], "test-model")
        self.assertEqual(insight["verification"]["method"], "agent_and_code")
        self.assertEqual(insight["verification"]["rejected_claims"], [])
        self.assertEqual(result["error"], None)
        check_result(request, result)
        self.assertEqual(len(transport.requests), 3)
        for body in transport.requests:
            self.assertEqual(body["response_format"], {"type": "json_object"})
            self.assertEqual(body["thinking"], {"type": "disabled"})

    async def test_roles_get_different_system_prompts_and_inputs(self):
        request = load_request()
        provider, transport = provider_for([GOOD_CLAIMS, GOOD_NARRATIVES, GOOD_AUDIT])
        await analyze(request, config=config(), provider=provider)
        systems = [body["messages"][0]["content"] for body in transport.requests]
        self.assertEqual(len(set(systems)), 3, "each role must have its own instructions")
        self.assertIn("analyst", systems[0].lower())
        self.assertIn("narrator", systems[1].lower())
        self.assertIn("auditor", systems[2].lower())
        # The auditor must actually receive the claims and the narratives to judge them.
        self.assertIn("NARRATIVES", transport.requests[2]["messages"][1]["content"])

    async def test_traces_record_each_real_agent(self):
        request = load_request()
        provider, _ = provider_for([GOOD_CLAIMS, GOOD_NARRATIVES, GOOD_AUDIT])
        result = await analyze(request, config=config(), provider=provider)
        agents = [(t["agent"], t["status"]) for t in result["traces"]]
        self.assertIn(("analyst", "completed"), agents)
        self.assertIn(("narrator", "completed"), agents)
        self.assertIn(("auditor", "completed"), agents)
        for trace in result["traces"]:
            self.assertEqual(trace["task_id"], request["task_id"])


class BoundedFailureTests(unittest.IsolatedAsyncioTestCase):
    async def test_non_json_content_falls_back(self):
        request = load_request()
        transport = httpx.MockTransport(lambda r: httpx.Response(
            200, json=envelope("this is not json at all")))
        provider = ChatCompletionsProvider(config(), transport=transport)
        result = await analyze(request, config=config(), provider=provider)
        self.assertEqual(result["status"], "fallback")
        self.assertEqual(result["insight"]["generation"]["mode"], "rule_fallback")
        check_result(request, result)

    async def test_empty_content_falls_back(self):
        request = load_request()
        transport = httpx.MockTransport(lambda r: httpx.Response(200, json=envelope("")))
        provider = ChatCompletionsProvider(config(), transport=transport)
        result = await analyze(request, config=config(), provider=provider)
        self.assertEqual(result["status"], "fallback")

    async def test_http_401_is_sanitised_and_never_leaks_the_key(self):
        request = load_request()
        transport = httpx.MockTransport(lambda r: httpx.Response(401, json={"error": "nope"}))
        provider = ChatCompletionsProvider(config(), transport=transport)
        result = await analyze(request, config=config(), provider=provider)
        self.assertEqual(result["status"], "fallback")
        blob = json.dumps(result)
        self.assertNotIn("sk-not-a-real-key", blob)
        self.assertNotIn("Bearer", blob)

    async def test_timeout_returns_fallback_and_says_why(self):
        request = load_request()
        failing = FailingTransport(httpx.ReadTimeout("slow"))
        provider = ChatCompletionsProvider(config(timeout=0.5), transport=failing.build())
        result = await analyze(request, config=config(timeout=0.5), provider=provider)
        self.assertEqual(result["status"], "fallback")
        self.assertEqual(result["error"]["code"], "TIMEOUT")
        check_result(request, result)

    async def test_network_error_falls_back_without_raising(self):
        request = load_request()
        failing = FailingTransport(httpx.ConnectError("down"))
        provider = ChatCompletionsProvider(config(), transport=failing.build())
        result = await analyze(request, config=config(), provider=provider)
        self.assertEqual(result["status"], "fallback")
        self.assertEqual(result["error"]["code"], "MODEL_UNAVAILABLE")


class CorrectionBudgetTests(unittest.IsolatedAsyncioTestCase):
    async def test_one_correction_recovers_a_bad_first_attempt(self):
        request = load_request()
        bad = {"claims": [dict(GOOD_CLAIMS["claims"][0], metric_value=9)]}
        provider, transport = provider_for([bad, GOOD_CLAIMS, GOOD_NARRATIVES, GOOD_AUDIT])
        result = await analyze(request, config=config(), provider=provider)
        self.assertEqual(result["status"], "passed")
        self.assertEqual(len(transport.requests), 4)
        notes = " ".join(t.get("note", "") for t in result["traces"])
        self.assertIn("rejected=1", notes)

    async def test_correction_is_capped_at_one_round(self):
        request = load_request()
        bad = {"claims": [dict(GOOD_CLAIMS["claims"][0], metric_value=9)]}
        provider, transport = provider_for([bad, bad])
        result = await analyze(request, config=config(), provider=provider)
        self.assertEqual(result["status"], "fallback")
        self.assertEqual(len(transport.requests), 2, "must not loop past one correction")
        self.assertEqual(result["insight"]["verification"]["status"], "fallback")

    async def test_auditor_rejection_triggers_a_cheap_repair_not_a_full_reanalysis(self):
        request = load_request()
        rejected_audit = {"approved": False, "rejected_claims": ["C2"],
                          "narrative_problems": ["claims causality"], "issues": ["overreach"]}
        # After the auditor objects, the repair is a single narrator rewrite of the
        # surviving claims: dropping the refused claim, not re-running the analyst.
        provider, transport = provider_for(
            [GOOD_CLAIMS, GOOD_NARRATIVES, rejected_audit, GOOD_NARRATIVES])
        result = await analyze(request, config=config(), provider=provider)
        self.assertEqual(result["status"], "passed")
        self.assertEqual(len(transport.requests), 4, "one auditor repair, then stop")
        self.assertTrue(any(t["agent"] == "auditor" and t["status"] == "rejected"
                            for t in result["traces"]))
        insight = result["insight"]
        self.assertEqual(insight["verification"]["status"], "passed")
        self.assertEqual(insight["verification"]["rejected_claims"], ["C2"])
        self.assertNotIn("C2", [c["claim_id"] for c in insight["claims"]])
        check_result(request, result)

    async def test_persistent_auditor_rejection_falls_back(self):
        request = load_request()
        rejected_audit = {"approved": False, "rejected_claims": ["C2"],
                          "narrative_problems": [], "issues": ["overreach"]}
        # Repair returns prose that still fails code verification -> honest fallback.
        provider, _ = provider_for(
            [GOOD_CLAIMS, GOOD_NARRATIVES, rejected_audit,
             {"casual": "They had 12 shots.", "analyst": "Two shots."}])
        result = await analyze(request, config=config(), provider=provider)
        self.assertEqual(result["status"], "fallback")
        self.assertEqual(result["insight"]["verification"]["rejected_claims"], ["C2"])
        check_result(request, result)


class VerificationUnitTests(unittest.TestCase):
    def test_invented_event_id_is_rejected(self):
        request = load_request()
        claims = copy.deepcopy(GOOD_CLAIMS["claims"])
        claims[0]["evidence_event_ids"] = ["MM-DEMO-01-E999"]
        approved, rejected, issues = check_claims(claims, request)
        self.assertEqual(rejected, ["C1"])
        self.assertTrue(any("outside the window" in issue for issue in issues))

    def test_wrong_metric_number_is_rejected(self):
        request = load_request()
        claims = [dict(GOOD_CLAIMS["claims"][0], metric_value=4)]
        approved, rejected, issues = check_claims(claims, request)
        self.assertEqual(rejected, ["C1"])
        self.assertTrue(any("does not equal" in issue for issue in issues))

    def test_interpretation_carrying_a_number_is_rejected(self):
        request = load_request()
        claims = [dict(GOOD_CLAIMS["claims"][1], metric_key="high_recoveries", metric_value=3)]
        approved, rejected, issues = check_claims(claims, request)
        self.assertEqual(rejected, ["C2"])

    def test_unsupported_causal_inference_is_rejected(self):
        request = load_request()
        claims = [dict(GOOD_CLAIMS["claims"][0]),
                  dict(GOOD_CLAIMS["claims"][1],
                       text="The opponent was clearly fatigued and the coach decided to press.")]
        approved, rejected, issues = check_claims(claims, request)
        self.assertEqual(rejected, ["C2"])
        self.assertTrue(any("unsupported cause" in issue for issue in issues))

    def test_interpretation_with_a_stray_number_is_rejected(self):
        request = load_request()
        claims = [dict(GOOD_CLAIMS["claims"][0]),
                  dict(GOOD_CLAIMS["claims"][1], text="Momentum shifted after 47 seconds.")]
        approved, rejected, issues = check_claims(claims, request)
        self.assertEqual(rejected, ["C2"])
        self.assertTrue(any("unsupported numbers" in issue for issue in issues))

    def test_metric_claim_must_state_its_number(self):
        request = load_request()
        claims = [dict(GOOD_CLAIMS["claims"][0], text="The side pressed high repeatedly.")]
        approved, rejected, issues = check_claims(claims, request)
        self.assertEqual(rejected, ["C1"])

    def test_metric_claim_stating_the_wrong_number_is_rejected(self):
        request = load_request()
        claims = [dict(GOOD_CLAIMS["claims"][0], text="The side made 4 high recoveries.")]
        approved, rejected, issues = check_claims(claims, request)
        self.assertEqual(rejected, ["C1"])

    def test_a_zero_metric_may_be_written_without_a_digit(self):
        """Regression: 'away_shots = 0' was rejected because good English and Chinese
        sentences say 'took no shots' / '没有完成任何射门' instead of writing 0."""
        request = load_request()
        claims = [{"claim_id": "C1", "kind": "metric",
                   "text": "AWAY took no shots in this window.",
                   "metric_key": "away_shots", "metric_value": 0,
                   "evidence_event_ids": ["MM-DEMO-01-E003"]},
                  {"claim_id": "C2", "kind": "metric",
                   "text": "客队在本窗口内没有完成任何射门。",
                   "metric_key": "away_shots", "metric_value": 0,
                   "evidence_event_ids": ["MM-DEMO-01-E003"]}]
        approved, rejected, issues = check_claims(claims, request)
        self.assertEqual(rejected, [], issues)
        self.assertEqual(len(approved), 2)

    def test_zero_metric_still_requires_a_positive_metric_claim_to_exist(self):
        request = load_request()
        claims = [{"claim_id": "C1", "kind": "metric",
                   "text": "AWAY took no shots in this window.",
                   "metric_key": "away_shots", "metric_value": 0,
                   "evidence_event_ids": ["MM-DEMO-01-E003"]}]
        approved, rejected, issues = check_claims(claims, request)
        self.assertEqual(rejected, [])
        self.assertEqual(len(approved), 1)

    def test_states_value_helper(self):
        from ai.verify import states_value
        self.assertTrue(states_value("3 high recoveries", 3))
        self.assertFalse(states_value("4 high recoveries", 3))
        self.assertTrue(states_value("took no shots", 0))
        self.assertTrue(states_value("没有完成任何射门", 0))
        self.assertFalse(states_value("took 2 shots", 0))

    def test_narrative_stray_number_is_caught(self):
        request = load_request()
        claims, _, _ = check_claims(GOOD_CLAIMS["claims"], request)
        narratives, issues = check_narratives(
            {"casual": "They had 12 shots.", "analyst": "Three recoveries led to two shots."},
            request, claims)
        self.assertIsNone(narratives)
        self.assertTrue(any("unsupported numbers" in issue for issue in issues))

    def test_narrative_event_id_leak_is_caught(self):
        request = load_request()
        claims, _, _ = check_claims(GOOD_CLAIMS["claims"], request)
        narratives, issues = check_narratives(
            {"casual": "See MM-DEMO-01-E007.", "analyst": "Three recoveries, two shots."},
            request, claims)
        self.assertIsNone(narratives)

    def test_number_words_and_chinese_numerals_are_read(self):
        self.assertIn(3.0, numbers_in("three recoveries"))
        self.assertIn(15.0, numbers_in("within 15 seconds"))
        self.assertIn(2.0, numbers_in("两次射门"))
        self.assertIn(15.0, numbers_in("十五秒内"))

    def test_ascii_digits_inside_chinese_prose_are_read(self):
        """Regression: a \\w lookbehind treats CJK as a word character and silently
        drops every digit embedded in Chinese prose, which made the whole Chinese path
        fail numeric verification."""
        self.assertEqual(numbers_in("在1500秒到1650秒这150秒窗口内，AWAY控球时间为115秒。"),
                         {1500.0, 1650.0, 150.0, 115.0})
        self.assertEqual(numbers_in("主场控球时间为35秒，共2次射门。"), {35.0, 2.0})
        # Chinese punctuation directly before a digit must not hide it either.
        self.assertEqual(numbers_in("（3次高位夺回）"), {3.0})

    def test_chinese_stray_number_is_still_caught(self):
        request = load_request()
        claims, _, _ = check_claims(GOOD_CLAIMS["claims"], request)
        narratives, issues = check_narratives(
            {"casual": "他们射门 12 次。", "analyst": "三次夺回，两次射门。"}, request, claims)
        self.assertIsNone(narratives)
        self.assertTrue(any("unsupported numbers" in issue for issue in issues))

    def test_chinese_narrative_with_only_allowed_numbers_is_accepted(self):
        request = load_request()
        request["language"] = "zh"
        claims, _, _ = check_claims(GOOD_CLAIMS["claims"], request)
        narratives, issues = check_narratives(
            {"casual": "主队在前场赢回球权三次。",
             "analyst": "本窗口记录到 3 次高位夺回，其中 2 次在 15 秒内形成射门。"},
            request, claims)
        self.assertEqual(issues, [])
        self.assertIsNotNone(narratives)

    def test_event_ids_are_not_mistaken_for_numbers(self):
        self.assertEqual(stray_numbers("event MM-DEMO-01-E007 fired", load_request()), [])

    def test_allowed_numbers_contains_every_metric(self):
        request = load_request()
        allowed = allowed_numbers(request)
        for value in request["metrics"].values():
            self.assertIn(float(value), allowed)


class ToolboxTests(unittest.TestCase):
    def setUp(self):
        self.request = load_request()
        self.box = Toolbox(self.request)

    def test_tools_are_scoped_to_the_request(self):
        self.assertEqual(self.box.get_metrics(), self.request["metrics"])
        events = self.box.get_event_window(1500, 1650)
        self.assertEqual(len(events), len(self.request["events"]))

    def test_window_request_is_clamped_not_widened(self):
        events = self.box.get_event_window(0, 100000)
        self.assertEqual(len(events), len(self.request["events"]))

    def test_reversed_window_raises(self):
        with self.assertRaises(ValueError):
            self.box.get_event_window(1600, 1500)

    def test_unknown_tool_raises(self):
        with self.assertRaises(ValueError):
            self.box.dispatch("rm_rf", {})

    def test_candidate_moments_match_the_frozen_metrics(self):
        moments = self.box.get_candidate_moments()
        self.assertEqual(len(moments), self.request["metrics"]["high_recoveries"])
        self.assertEqual(sum(1 for m in moments if m["linked_shot_event_ids"]),
                         self.request["metrics"]["linked_shots"])


class ToolLoopTests(unittest.IsolatedAsyncioTestCase):
    async def test_tool_calls_are_executed_and_bounded(self):
        request = load_request()
        messages = []

        def handler(http_request):
            body = json.loads(http_request.content.decode("utf-8"))
            messages.append(body)
            if len(messages) == 1:
                return httpx.Response(200, json=envelope("", model="test-model") | {"choices": [{
                    "message": {"role": "assistant", "content": "",
                                "tool_calls": [{"id": "call-1", "type": "function",
                                                "function": {"name": "get_metrics", "arguments": "{}"}}]}}]})
            return httpx.Response(200, json=envelope(json.dumps(
                {"claims": [{"claim_id": "C1", "kind": "metric",
                             "text": "3 high recoveries.",
                             "metric_key": "high_recoveries", "metric_value": 3,
                             "evidence_event_ids": ["MM-DEMO-01-E007"]}]})))

        provider = ChatCompletionsProvider(config(), transport=httpx.MockTransport(handler))
        box = Toolbox(request)
        from ai.tools import TOOL_SCHEMAS
        result = await provider.complete_with_tools(
            system="s", user="u", deadline=__import__("time").monotonic() + 10,
            toolbox=box, tool_schemas=TOOL_SCHEMAS, max_tool_calls=2)
        self.assertIn("claims", result)
        self.assertEqual(box.calls, ["get_metrics"])
        self.assertIn("tools", messages[0])
        self.assertEqual(len(messages), 2)


if __name__ == "__main__":
    unittest.main()
