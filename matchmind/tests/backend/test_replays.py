import asyncio
import copy
import unittest
from dataclasses import replace

from backend.app import ROOT
from backend.data import Catalog
from backend.http import ApiError
from backend.replays import Replays
from backend.settings import Settings
from contracts.validation import check_shape


class ReplayTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.now = 100.0
        self.store = Replays(Catalog(ROOT / "data/fixtures"), clock=lambda: self.now)
        self.body = {"match_id": "MM-DEMO-01", "speed": 5}
        self.initial = await self.store.create(self.body)
        self.rid = self.initial["replay"]["replay_id"]

    async def asyncTearDown(self):
        await self.store.close()

    async def test_play_pause_speed_and_two_session_isolation(self):
        other = await self.store.create(self.body)
        await self.store.control(self.rid, {"action": "play"})
        self.now += 10
        snap = await self.store.control(self.rid, {"action": "pause"})
        self.assertEqual(snap["replay"]["clock_sec"], 1550)
        self.now += 100
        self.assertEqual((await self.store.get(self.rid))["replay"]["clock_sec"], 1550)
        await self.store.control(self.rid, {"action": "set_speed", "speed": 10})
        await self.store.control(self.rid, {"action": "play"})
        self.now += 10
        self.assertEqual((await self.store.get(self.rid))["replay"]["clock_sec"], 1650)
        self.assertEqual((await self.store.get(other["replay"]["replay_id"]))["replay"]["clock_sec"], 1500)

    async def test_end_requires_reset_and_reset_keeps_lifetime_sequence(self):
        await self.store.control(self.rid, {"action": "play"})
        self.now += 100
        before = await self.store.get(self.rid)
        self.assertEqual(before["replay"]["status"], "ended")
        with self.assertRaises(ApiError) as error:
            await self.store.control(self.rid, {"action": "play"})
        self.assertEqual(error.exception.status, 409)
        after = await self.store.control(self.rid, {"action": "reset"})
        check_shape("ReplaySnapshot", after)
        self.assertEqual((after["replay"]["run_id"], after["replay"]["clock_sec"]), (2, 1500))
        self.assertGreater(after["replay"]["last_seq"], before["replay"]["last_seq"])
        self.assertEqual(after["state"]["shots"], {"HOME": 0, "AWAY": 0})

    async def test_create_and_reset_idempotency_and_old_run_guard(self):
        a, b = await asyncio.gather(self.store.create(self.body, "key"), self.store.create(self.body, "key"))
        self.assertEqual(a, b)
        with self.assertRaises(ApiError) as error:
            await self.store.create(self.body | {"speed": 1}, "key")
        self.assertEqual(error.exception.status, 409)
        first = await self.store.control(self.rid, {"action": "reset"}, "reset-key", 1)
        retry = await self.store.control(self.rid, {"action": "reset"}, "reset-key", 1)
        self.assertEqual(first, retry)
        self.assertEqual(first["replay"]["run_id"], 2)
        with self.assertRaises(ApiError) as error:
            await self.store.control(self.rid, {"action": "reset"}, "other-key", 1)
        self.assertEqual(error.exception.status, 409)

    async def test_subscribers_receive_independently_and_reconnect_is_snapshot(self):
        sid1, q1 = await self.store.subscribe(self.rid)
        sid2, q2 = await self.store.subscribe(self.rid)
        for q in (q1, q2):
            message = q.get_nowait()
            check_shape("StreamMessage", message)
            self.assertEqual(message["seq"], message["payload"]["replay"]["last_seq"])
        await self.store.control(self.rid, {"action": "play"})
        self.now += 30
        await self.store.tick()
        messages1, messages2 = [], []
        for q, messages in ((q1, messages1), (q2, messages2)):
            while not q.empty():
                messages.append(q.get_nowait())
            for message in messages:
                check_shape("StreamMessage", message)
        self.assertEqual(messages1, messages2)
        self.assertEqual(messages1[-1]["payload"]["replay"]["clock_sec"], 1650)
        await self.store.unsubscribe(self.rid, sid1)
        sid3, q3 = await self.store.subscribe(self.rid)
        recovered = q3.get_nowait()
        self.assertEqual(recovered["kind"], "snapshot")
        self.assertEqual(recovered["payload"]["state"]["shots"]["HOME"], 2)
        await self.store.control(self.rid, {"action": "reset"})
        # Reset drains queued prior-generation messages on every active subscriber.
        self.assertEqual(q2.get_nowait()["run_id"], 2)
        self.assertEqual(q3.get_nowait()["run_id"], 2)

    async def test_slow_subscriber_is_disconnected_without_blocking_other(self):
        sid1, slow = await self.store.subscribe(self.rid)
        sid2, fast = await self.store.subscribe(self.rid)
        first = slow.get_nowait()
        fast.get_nowait()
        while not slow.full():
            slow.put_nowait(first)
        await self.store.control(self.rid, {"action": "play"})
        self.assertIsNone(slow.get_nowait())
        self.assertIsNotNone(fast.get_nowait())
        self.assertNotIn(sid1, self.store.sessions[self.rid].subscribers)
        self.assertIn(sid2, self.store.sessions[self.rid].subscribers)

    async def test_capacity_expiry_and_idempotency_do_not_resurrect_session(self):
        self.store.settings = replace(Settings(), max_sessions=1, session_ttl=5)
        with self.assertRaises(ApiError) as error:
            await self.store.create(self.body)
        self.assertEqual(error.exception.status, 429)
        self.now += 6
        await self.store.tick()
        with self.assertRaises(ApiError) as error:
            await self.store.get(self.rid)
        self.assertEqual(error.exception.status, 404)
        created = await self.store.create(self.body, "expire-key")
        self.now += 6
        await self.store.tick()
        with self.assertRaises(ApiError) as error:
            await self.store.create(self.body, "expire-key")
        self.assertEqual(error.exception.status, 404)
        self.assertNotIn(created["replay"]["replay_id"], self.store.sessions)

    async def test_existing_ai_stub_input_output_and_reset_boundary_without_a_key(self):
        from ai.service import analyze
        with self.assertRaises(ApiError):
            await self.store.analysis_request(self.rid)
        await self.store.control(self.rid, {"action": "play"})
        self.now += 30
        await self.store.control(self.rid, {"action": "pause"})
        request = await self.store.analysis_request(self.rid)
        result = await analyze(request)  # The unchanged frozen implementation is offline only.
        self.assertEqual(result["status"], "fallback")
        self.assertTrue(await self.store.publish_analysis(request, result))
        self.assertFalse(await self.store.publish_analysis(request, result))
        self.assertEqual(len((await self.store.get(self.rid))["insights"]), 1)
        malformed = copy.deepcopy(result)
        malformed["run_id"] += 1
        with self.assertRaises(ValueError):
            await self.store.publish_analysis(request, malformed)
        await self.store.control(self.rid, {"action": "reset"})
        self.assertFalse(await self.store.publish_analysis(request, result))
        self.assertEqual((await self.store.get(self.rid))["insights"], [])


if __name__ == "__main__":
    unittest.main()
