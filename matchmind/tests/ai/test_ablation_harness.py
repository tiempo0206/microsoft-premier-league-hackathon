"""The ablation harness itself, tested offline.

An indentation bug once put the row-recording lines outside the window loop and wasted a
25-minute paid run before crashing on the last variant. The harness is expensive to execute, so
it needs a cheap test that exercises its control flow without a model.
"""
import asyncio
import copy
import json
import unittest
from dataclasses import replace
from pathlib import Path
from unittest import mock

from ai.config import ModelConfig
from evaluation import ablation

ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = json.loads((ROOT / "contracts/examples/analysis_result.json").read_text(encoding="utf-8"))


def stub_result(status="fallback"):
    result = copy.deepcopy(EXAMPLE)
    result["status"] = status
    return result


class HarnessTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.config = ModelConfig(provider="test", base_url="https://example.invalid",
                                  model="test-model", api_key="sk-test", timeout=5.0,
                                  orchestrator="direct")

    def patch_analyze(self, behaviour):
        return mock.patch.object(ablation, "analyze", behaviour)

    async def test_a_clean_run_records_one_row_per_window_per_repeat(self):
        async def fake(request, config=None, provider=None):
            return stub_result()

        with self.patch_analyze(fake), \
                mock.patch.object(ablation, "ChatCompletionsProvider", lambda cfg: object()):
            rows = await ablation.run_variant("full", {}, self.config, limit=2, repeats=2)

        self.assertEqual(len(rows), 4)
        for row in rows:
            for key in ("window", "repeat", "status", "elapsed_ms", "agent_calls", "score"):
                self.assertIn(key, row)
            self.assertEqual(row["status"], "fallback")
            self.assertTrue(row["score"]["published"])
        self.assertEqual([r["repeat"] for r in rows], [0, 0, 1, 1])

    async def test_a_raising_window_is_recorded_as_a_crash_and_does_not_abort_the_run(self):
        calls = {"n": 0}

        async def flaky(request, config=None, provider=None):
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("model exploded")
            return stub_result()

        with self.patch_analyze(flaky), \
                mock.patch.object(ablation, "ChatCompletionsProvider", lambda cfg: object()):
            rows = await ablation.run_variant("full", {}, self.config, limit=2, repeats=2)

        self.assertEqual(len(rows), 4, "a crash must not truncate the run")
        self.assertEqual(rows[0]["status"], "CRASH")
        self.assertIn("RuntimeError", rows[0]["error"])
        self.assertFalse(rows[0]["score"]["published"])
        self.assertEqual(rows[-1]["status"], "fallback")

    async def test_the_patch_is_always_restored_even_when_the_run_raises(self):
        original = ablation.service_module.check_claims

        async def boom(request, config=None, provider=None):
            raise RuntimeError("boom")

        spec = {"patch": {"check_claims": lambda raw, req: ([], [], [])}}
        with self.patch_analyze(boom), \
                mock.patch.object(ablation, "ChatCompletionsProvider", lambda cfg: object()):
            await ablation.run_variant("no_code_gate", copy.deepcopy(spec), self.config,
                                       limit=1, repeats=1)
        self.assertIs(ablation.service_module.check_claims, original,
                      "the monkeypatch leaked past the variant")

    def test_summary_reports_per_repeat_spread(self):
        rows = [
            {"window": "A", "repeat": 0, "status": "fallback", "elapsed_ms": 1,
             "agent_calls": 1, "score": {"published": True, "code_rejected_claims": [],
                                          "narrative_issues": [], "universal_quantifier": False}},
            {"window": "A", "repeat": 1, "status": "passed", "elapsed_ms": 1,
             "agent_calls": 1, "score": {"published": True, "code_rejected_claims": [],
                                          "narrative_issues": [], "universal_quantifier": False}},
            {"window": "B", "repeat": 0, "status": "passed", "elapsed_ms": 1,
             "agent_calls": 1, "score": {"published": True, "code_rejected_claims": [],
                                          "narrative_issues": [], "universal_quantifier": False}},
        ]
        summary = ablation.summarise({"full": rows}, repeats=2)["full"]
        self.assertEqual(summary["fallback_per_repeat"], [1, 0])
        self.assertEqual(summary["fallback_spread"], 1)
        self.assertEqual(summary["published"], 3)

    def test_repeats_argument_is_parsed_from_the_command_line(self):
        """`python -m` passes argv=None; the earlier version then silently ran one repeat."""
        self.assertEqual(ablation.args_value(["--repeats", "3"], "--repeats", 1), 3)
        self.assertEqual(ablation.args_value([], "--repeats", 1), 1)
        self.assertEqual(ablation.args_value(["--windows", "2"], "--windows", 6), 2)

    def test_main_reads_sys_argv_when_none_is_passed(self):
        import inspect
        source = inspect.getsource(ablation.main)
        self.assertIn("sys.argv[1:]", source)

    def test_the_caveat_text_travels_with_every_report(self):
        """The caveat must state what the numbers support AND what they do not, so a reader
        cannot quote the repair result and then imply the other variants were measured."""
        self.assertIn("WHAT THE MEASUREMENTS SUPPORT", ablation.CAVEATS)
        self.assertIn("WHAT THEY DO NOT SUPPORT", ablation.CAVEATS)
        self.assertIn("repair round", ablation.CAVEATS)
        self.assertIn("factcheck_bench", ablation.CAVEATS)
        self.assertIn("repeats 3", ablation.CAVEATS)


if __name__ == "__main__":
    unittest.main()
