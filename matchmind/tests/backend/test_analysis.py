import asyncio
import unittest
from dataclasses import replace

from ai.service import analyze as offline_stub
from backend.analysis import AnalysisDispatcher
from backend.audit import ROOT
from backend.data import Catalog
from backend.replays import Replays
from backend.settings import Settings
from contracts.validation import check_shape


class DispatchTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.now, self.calls = 100.0, []
        async def adapter(request):
            self.calls.append(request)
            return await offline_stub(request)
        self.settings = replace(Settings(), analysis_timeout=12)
        self.store = Replays(Catalog(ROOT / "data/extra/validated-demo"), self.settings, lambda: self.now)
        self.dispatcher = AnalysisDispatcher(self.store, adapter, "precomputed", lambda: self.now)
        self.store.analysis_hook = self.dispatcher.enqueue
        self.store.analysis_invalidator = self.dispatcher.invalidate
        await self.dispatcher.start()
        initial = await self.store.create({"match_id": "MM-DEMO-01", "speed": 5})
        self.rid = initial["replay"]["replay_id"]

    async def asyncTearDown(self):
        await self.dispatcher.close()
        await self.store.close()

    async def trigger(self, replay_id=None, pause=True):
        replay_id = replay_id or self.rid
        await self.store.control(replay_id, {"action": "play"})
        self.now += 30
        await self.store.tick()
        if pause:
            await self.store.control(replay_id, {"action": "pause"})

    async def settled(self):
        await asyncio.wait_for(self.dispatcher.queue.join(), timeout=10)

    async def test_fixed_window_once_and_precomputed_label_in_stream(self):
        _, queue = await self.store.subscribe(self.rid)
        await self.trigger()
        await self.settled()
        for _ in range(3):
            await self.store.get(self.rid)
            await self.store.tick()
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.calls[0]["window"], {"start_sec": 1500, "end_sec": 1650})
        self.assertEqual(len(self.calls[0]["events"]), 20)
        snap = await self.store.get(self.rid)
        self.assertEqual(snap["insights"][0]["generation"]["mode"], "precomputed")
        self.assertEqual(snap["replay"]["status"], "paused")
        messages = []
        while not queue.empty():
            messages.append(queue.get_nowait())
        for message in messages:
            check_shape("StreamMessage", message)
        self.assertTrue(any(message["kind"] == "insight" for message in messages))
        await self.store.control(self.rid, {"action": "reset"})
        await self.trigger()
        await self.settled()
        self.assertEqual(len(self.calls), 2)
        self.assertEqual((await self.store.get(self.rid))["replay"]["run_id"], 2)

    async def test_late_result_after_reset_cannot_publish(self):
        started, release = asyncio.Event(), asyncio.Event()
        async def late(request):
            started.set()
            try:
                await release.wait()
            except asyncio.CancelledError:
                await release.wait()  # Simulate an adapter whose cancellation is delayed.
            return await offline_stub(request)
        self.dispatcher.analyzer = late
        await self.trigger()
        await asyncio.wait_for(started.wait(), 1)
        await self.store.control(self.rid, {"action": "reset"})
        release.set()
        await self.settled()
        self.assertEqual((await self.store.get(self.rid))["insights"], [])

    async def test_timeout_does_not_stop_replay(self):
        _, queue = await self.store.subscribe(self.rid)
        self.dispatcher.settings = replace(self.settings, analysis_timeout=0.02)
        async def never(request):
            await asyncio.Event().wait()
        self.dispatcher.analyzer = never
        await self.trigger(pause=False)
        await self.settled()
        self.now += 1
        snap = await self.store.get(self.rid)
        self.assertEqual(snap["replay"]["clock_sec"], 1655)
        self.assertEqual(snap["insights"], [])
        messages = []
        while not queue.empty():
            messages.append(queue.get_nowait())
        self.assertTrue(any(m["kind"] == "error" and m["payload"]["code"] == "TIMEOUT" for m in messages))

    async def test_bad_output_and_adapter_exception_are_sanitized(self):
        _, queue = await self.store.subscribe(self.rid)
        async def malformed(request):
            result = await offline_stub(request)
            result["insight"]["metrics"]["linked_shots"] = 99
            return result
        self.dispatcher.analyzer = malformed
        await self.trigger()
        await self.settled()
        errors = []
        while not queue.empty():
            message = queue.get_nowait()
            if message["kind"] == "error": errors.append(message["payload"])
        self.assertEqual(errors[-1]["code"], "MODEL_INVALID_OUTPUT")
        await self.store.control(self.rid, {"action": "reset"})
        async def failed(request):
            raise RuntimeError("adapter-internal-sensitive-value")
        self.dispatcher.analyzer = failed
        await self.trigger()
        await self.settled()
        while not queue.empty():
            message = queue.get_nowait()
            if message["kind"] == "error": errors.append(message["payload"])
        self.assertEqual(errors[-1]["code"], "MODEL_UNAVAILABLE")
        self.assertNotIn("sensitive", str(errors))

    async def test_budget_deduplication_and_queue_bounds(self):
        self.dispatcher.settings = replace(self.settings, analysis_limit_per_hour=1)
        self.assertIsNone(self.dispatcher.enqueue(self.rid, 1))
        self.assertIsNone(self.dispatcher.enqueue(self.rid, 1))
        self.assertEqual(self.dispatcher.used, 1)
        rejected = self.dispatcher.enqueue("another-replay", 1)
        self.assertEqual(rejected["code"], "CAPACITY_LIMIT")
        self.assertEqual(self.dispatcher.used, 1)

    async def test_queue_wait_is_part_of_total_deadline(self):
        self.dispatcher.enqueue(self.rid, 1)
        self.now += self.settings.analysis_timeout + 1
        await self.settled()
        self.assertEqual(self.calls, [])

    async def test_adapter_return_after_deadline_is_not_published(self):
        async def late(request):
            self.now += self.settings.analysis_timeout + 1
            return await offline_stub(request)
        self.dispatcher.analyzer = late
        _, queue = await self.store.subscribe(self.rid)
        await self.trigger()
        await self.settled()
        self.assertEqual((await self.store.get(self.rid))["insights"], [])
        errors = []
        while not queue.empty():
            message = queue.get_nowait()
            if message["kind"] == "error": errors.append(message["payload"])
        self.assertEqual(errors[-1]["code"], "TIMEOUT")

    async def test_queue_capacity_rejection_does_not_consume_budget(self):
        self.dispatcher.queue = asyncio.Queue(maxsize=1)
        self.dispatcher.settings = replace(self.settings, analysis_limit_per_hour=10)
        self.assertIsNone(self.dispatcher.enqueue(self.rid, 1))
        self.assertEqual(self.dispatcher.enqueue("other-replay", 1)["code"], "CAPACITY_LIMIT")
        self.assertEqual(self.dispatcher.used, 1)

    async def test_two_sessions_respect_single_adapter_concurrency(self):
        started, release = asyncio.Event(), asyncio.Event()
        active, maximum = 0, 0
        async def bounded(request):
            nonlocal active, maximum
            active += 1
            maximum = max(maximum, active)
            started.set()
            await release.wait()
            active -= 1
            return await offline_stub(request)
        self.dispatcher.analyzer = bounded
        other = await self.store.create({"match_id": "MM-DEMO-01", "speed": 5})
        await self.store.control(self.rid, {"action": "play"})
        await self.store.control(other["replay"]["replay_id"], {"action": "play"})
        self.now += 30
        await self.store.tick()
        await asyncio.wait_for(started.wait(), 1)
        self.assertEqual(active, 1)
        release.set()
        await self.settled()
        self.assertEqual(maximum, 1)
        for rid in (self.rid, other["replay"]["replay_id"]):
            self.assertEqual(len((await self.store.get(rid))["insights"]), 1)

    async def test_default_factory_disables_dispatch_and_injection_uses_lifespan(self):
        from backend.app import create_app
        self.assertIsNone(create_app().state.dispatcher)
        app = create_app(settings=self.settings, clock=lambda: self.now,
                         analyzer=offline_stub, analysis_source="precomputed")
        async with app.router.lifespan_context(app):
            self.assertEqual(len(app.state.dispatcher.workers), 1)
        self.assertEqual(app.state.dispatcher.workers, [])
