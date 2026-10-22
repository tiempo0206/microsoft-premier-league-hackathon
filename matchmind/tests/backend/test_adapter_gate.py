import socket
import unittest
from unittest.mock import patch

from deploy.adapter_check import check_adapter
from backend.showcase import build_packet


class AdapterGateTests(unittest.IsolatedAsyncioTestCase):
    async def test_network_and_secret_errors_are_not_forwarded(self):
        async def bad(request):
            socket.create_connection(("example.invalid", 443))
        report = await check_adapter(bad)
        self.assertEqual(report["status"], "blocked")
        self.assertEqual(report["model_calls"], 0)
        self.assertEqual(len(report["valid_request_failures"]), 12)
        self.assertTrue(all(row["reason"] == "network_attempt_blocked" for row in report["valid_request_failures"]))
        async def error(request):
            raise RuntimeError("private-token-placeholder-must-not-appear")
        report = await check_adapter(error)
        self.assertNotIn("private-token", str(report))

    async def test_malformed_adapter_output_and_missing_async_entry_are_blocked(self):
        async def malformed(request):
            return {"insight": {"claims": [{"evidence_event_ids": None}], "evidence_event_ids": []}}
        report = await check_adapter(malformed)
        self.assertEqual(report["status"], "blocked")
        self.assertEqual(len(report["valid_request_failures"]), 12)
        self.assertEqual((await check_adapter(lambda request: {}))["reason"], "C_adapter_must_be_async")
        packet = build_packet()
        async def mutating(request):
            request["metrics"]["high_recoveries"] = 999
            return {}
        with patch("deploy.adapter_check.build_packet", return_value=packet):
            await check_adapter(mutating)
        self.assertEqual(packet["requests"][0]["metrics"]["high_recoveries"], 3)

    async def test_startup_gate_for_showcase_blocks_before_starting_a_server(self):
        from deploy.release_run import main
        async def not_ready(*args):
            return {"status": "blocked"}
        with patch("deploy.release_run.build_report", return_value={"status": "passed"}), \
             patch("deploy.release_run.Settings.from_env") as settings, \
             patch("deploy.adapter_check.check_adapter", not_ready), \
             patch("deploy.release_run.asyncio.run", return_value={"status": "blocked"}) as run, \
             patch("deploy.release_run.uvicorn.run") as server, patch("builtins.print"):
            settings.return_value.data_directory = "data/extra/showcase/press"
            with self.assertRaises(SystemExit) as context:
                main()
            # Close the mocked-out coroutine; an event loop already runs in this test.
            run.call_args.args[0].close()
        self.assertEqual(context.exception.code, 2)
        server.assert_not_called()
