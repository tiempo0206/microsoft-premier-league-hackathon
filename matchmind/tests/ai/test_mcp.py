"""MCP surface tests. No model, no network, no server process.

The point of these tests is that the MCP tools and the product share one implementation:
if the statistics or the detector changed here, these assertions would catch the drift.
"""
import asyncio
import unittest

from ai import mcp_server


class CatalogueTests(unittest.TestCase):
    def test_list_matches_reports_declared_coverage(self):
        matches = mcp_server.list_matches()
        self.assertTrue(matches)
        for match in matches:
            self.assertLess(match["clip_start_sec"], match["clip_end_sec"])
            self.assertTrue(match["synthetic"])
            self.assertGreater(match["event_count"], 0)

    def test_unknown_match_is_an_error_not_an_empty_answer(self):
        with self.assertRaises(ValueError):
            mcp_server.get_metrics("NOPE", 1500, 1650)


class WindowTests(unittest.TestCase):
    def test_metrics_match_the_backend_oracle(self):
        payload = mcp_server.get_metrics("MM-DEMO-01", 1500, 1650, "HOME")
        self.assertEqual(payload["metrics"]["high_recoveries"], 3)
        self.assertEqual(payload["metrics"]["linked_shots"], 2)
        self.assertEqual(payload["metrics"]["home_shots"], 2)
        self.assertEqual(payload["metrics"]["away_shots"], 0)
        self.assertEqual(payload["consistency_issues"], [])

    def test_window_outside_the_clip_is_refused(self):
        with self.assertRaises(ValueError):
            mcp_server.get_metrics("MM-DEMO-01", 1400, 1650)
        with self.assertRaises(ValueError):
            mcp_server.get_metrics("MM-DEMO-01", 1500, 9999)

    def test_reversed_window_is_refused(self):
        with self.assertRaises(ValueError):
            mcp_server.get_metrics("MM-DEMO-01", 1650, 1500)

    def test_bad_team_is_refused(self):
        with self.assertRaises(ValueError):
            mcp_server.get_metrics("MM-DEMO-01", 1500, 1650, "BOTH")

    def test_event_window_returns_ordered_events(self):
        events = mcp_server.get_event_window("MM-DEMO-01", 1500, 1650)
        self.assertEqual(len(events), 20)
        stamps = [event["timestamp_sec"] for event in events]
        self.assertEqual(stamps, sorted(stamps))

    def test_candidate_moments_agree_with_the_metric_count(self):
        moments = mcp_server.get_candidate_moments("MM-DEMO-01", 1500, 1650, "HOME")
        metrics = mcp_server.get_metrics("MM-DEMO-01", 1500, 1650, "HOME")["metrics"]
        self.assertEqual(len(moments), metrics["high_recoveries"])
        self.assertEqual(sum(1 for m in moments if m["linked_shots"]), metrics["linked_shots"])

    def test_candidate_moments_expose_the_wider_context_link(self):
        """A tool result may say more than a metric may, as long as it keeps them apart.
        In the default window there is no shot after the 1640 recovery, so the context tier
        is correctly empty here - that absence is itself the documented window defect."""
        moments = mcp_server.get_candidate_moments("MM-DEMO-01", 1500, 1650, "HOME")
        self.assertTrue(all("sustained_shots" in m for m in moments))
        self.assertEqual(sum(1 for m in moments if m["sustained_shots"]), 2)


class ExplainTests(unittest.IsolatedAsyncioTestCase):
    async def test_explain_window_without_a_model_is_an_honest_fallback(self):
        payload = await asyncio.wait_for(
            mcp_server.explain_window("MM-DEMO-01", 1500, 1650, "HOME", "en", "MCP-TEST"), 60)
        result = payload["result"]
        self.assertIn(result["status"], ("fallback", "passed"))
        insight = result["insight"]
        self.assertIsNotNone(insight)
        self.assertIn(insight["generation"]["mode"], ("rule_fallback", "live_model"))
        if insight["generation"]["mode"] == "rule_fallback":
            self.assertEqual(insight["verification"]["method"], "code_only")
            self.assertIn("rule fallback", payload["note"])

    async def test_bad_language_is_refused(self):
        with self.assertRaises(ValueError):
            await mcp_server.explain_window("MM-DEMO-01", 1500, 1650, "HOME", "fr")


class RegistrationTests(unittest.TestCase):
    def test_all_tools_are_registered(self):
        tools = asyncio.run(mcp_server.server.list_tools())
        names = {tool.name for tool in tools}
        for expected in ("list_matches", "get_metrics", "get_event_window",
                         "get_candidate_moments", "explain_window"):
            self.assertIn(expected, names)

    def test_each_tool_documents_itself(self):
        tools = asyncio.run(mcp_server.server.list_tools())
        for tool in tools:
            self.assertTrue((tool.description or "").strip(), tool.name + " needs a description")


if __name__ == "__main__":
    unittest.main()
