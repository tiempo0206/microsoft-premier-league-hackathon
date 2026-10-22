"""Role B dispatch only: bounded handoff to an injected async AI module."""
import asyncio
import copy
import time

from contracts.validation import check_result


class AnalysisDispatcher:
    def __init__(self, store, analyzer, source="external", clock=time.monotonic):
        if source not in ("external", "precomputed"):
            raise ValueError("Analysis source must be external or precomputed")
        self.store, self.analyzer, self.source, self.clock = store, analyzer, source, clock
        self.settings = store.settings
        self.queue = asyncio.Queue(maxsize=self.settings.analysis_queue_size)
        self.pending, self.active = {}, {}
        self.workers = []
        self.closing = False
        self.bucket, self.used = None, 0

    def enqueue(self, replay_id, run_id):
        """Called inside the replay lock; no await or model call happens here."""
        key = replay_id, run_id
        if key in self.pending:
            return None
        now = self.clock()
        bucket = int(now // 3600)
        if bucket != self.bucket:
            self.bucket, self.used = bucket, 0
        if self.closing or not self.workers:
            return self.error("MODEL_UNAVAILABLE", "Analysis adapter is not running.")
        if self.queue.full() or self.used >= self.settings.analysis_limit_per_hour:
            return self.error("CAPACITY_LIMIT", "Analysis capacity is busy; replay continues.")
        self.pending[key] = now
        self.queue.put_nowait(key)
        self.used += 1
        return None

    def invalidate(self, replay_id, run_id):
        key = replay_id, run_id
        self.pending.pop(key, None)
        task = self.active.get(key)
        if task is not None:
            task.cancel()

    @staticmethod
    def error(code, message):
        return {"code": code, "message": message, "retryable": True}

    def normalize_result(self, request, result):
        check_result(request, result)
        result = copy.deepcopy(result)
        if self.source == "precomputed" and result["status"] != "rejected":
            generation = result["insight"]["generation"]
            if generation["mode"] == "live_model" or generation["model"] is not None:
                raise ValueError("Live output cannot be relabelled as precomputed")
            # The unchanged supplied stub loads a saved JSON result. Label that
            # configured adapter honestly, without changing C's module or text.
            generation["mode"] = "precomputed"
            check_result(request, result)
        return result

    async def start(self):
        if not self.workers:
            self.closing = False
            self.workers = [asyncio.create_task(self.work()) for _ in range(self.settings.analysis_concurrency)]

    async def work(self):
        while True:
            key = await self.queue.get()
            try:
                enqueued = self.pending.get(key)
                if enqueued is None:
                    continue
                remaining = self.settings.analysis_timeout - (self.clock() - enqueued)
                if remaining <= 0:
                    await self.store.analysis_error(*key, self.error("TIMEOUT", "Analysis queue deadline expired; replay continues."))
                    continue
                try:
                    request = await self.store.analysis_request(key[0])
                    if request["run_id"] != key[1]:
                        continue
                    remaining = self.settings.analysis_timeout - (self.clock() - enqueued)
                    if remaining <= 0:
                        await self.store.analysis_error(*key, self.error("TIMEOUT", "Analysis input deadline expired; replay continues."))
                        continue
                    task = asyncio.create_task(self.analyzer(copy.deepcopy(request)))
                    self.active[key] = task
                    result = await asyncio.wait_for(task, timeout=remaining)
                    # A cooperative adapter normally propagates cancellation.
                    # Even if it returns after swallowing it, never publish a
                    # result whose total queue/call deadline already elapsed.
                    if self.clock() - enqueued >= self.settings.analysis_timeout:
                        await self.store.analysis_error(*key, self.error("TIMEOUT", "Analysis deadline expired; replay continues."))
                        continue
                except asyncio.CancelledError:
                    if self.closing:
                        raise
                    # A reset/expiry cancelled this job. It is not an AI failure
                    # for the new generation, and must never emit into it.
                    continue
                except TimeoutError:
                    await self.store.analysis_error(*key, self.error("TIMEOUT", "Analysis timed out; replay continues."))
                    continue
                except Exception:
                    await self.store.analysis_error(*key, self.error("MODEL_UNAVAILABLE", "Analysis adapter failed; replay continues."))
                    continue
                try:
                    result = self.normalize_result(request, result)
                except Exception:
                    await self.store.analysis_error(*key, self.error("MODEL_INVALID_OUTPUT", "Analysis output failed contract checks."))
                    continue
                if result["status"] == "rejected":
                    code = (result["error"] or {}).get("code")
                    if code not in ("TIMEOUT", "MODEL_UNAVAILABLE", "MODEL_INVALID_OUTPUT", "CAPACITY_LIMIT"):
                        code = "MODEL_INVALID_OUTPUT"
                    await self.store.analysis_error(*key, self.error(code, "Analysis rejected this window; replay continues."))
                else:
                    await self.store.publish_analysis(request, result)
            finally:
                self.active.pop(key, None)
                self.pending.pop(key, None)
                self.queue.task_done()

    async def close(self):
        self.closing = True
        for task in self.workers:
            task.cancel()
        await asyncio.gather(*self.workers, return_exceptions=True)
        self.workers.clear()
        self.active.clear()
        self.pending.clear()
        while not self.queue.empty():
            self.queue.get_nowait()
            self.queue.task_done()
