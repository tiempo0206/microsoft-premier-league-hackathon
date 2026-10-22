"""Bounded in-memory replays. One asyncio lock, no network work inside it."""
import asyncio
import copy
import json
import time
import uuid
from dataclasses import dataclass, field

from .http import ApiError
from .settings import Settings
from .stats import state_at
from .stats import window_metrics
from contracts.validation import check_request, check_result, can_publish


@dataclass
class Session:
    fixture: object
    replay_id: str
    speed: int
    updated: float
    touched: float
    clock: float
    run_id: int = 1
    status: str = "idle"
    seq: int = 0
    next_event: int = 0
    last_snapshot: float = 0
    insights: list = field(default_factory=list)
    traces: list = field(default_factory=list)
    subscribers: dict = field(default_factory=dict)


class Replays:
    def __init__(self, catalog, settings=None, clock=time.monotonic):
        self.catalog, self.settings, self.clock = catalog, settings or Settings(), clock
        self.sessions, self.idempotency = {}, {}
        self.lock = asyncio.Lock()

    def _snapshot(self, session):
        replay = {"replay_id": session.replay_id, "run_id": session.run_id,
                  "match_id": session.fixture.match["match_id"], "clock_sec": int(session.clock),
                  "speed": session.speed, "status": session.status, "last_seq": session.seq}
        return {"replay": replay, "state": state_at(session.fixture, int(session.clock)),
                "insights": copy.deepcopy(session.insights), "traces": copy.deepcopy(session.traces)}

    @staticmethod
    def _stop(queue):
        while not queue.empty():
            queue.get_nowait()
        queue.put_nowait(None)

    def _message(self, session, kind, payload=None):
        session.seq += 1
        return {"replay_id": session.replay_id, "run_id": session.run_id, "seq": session.seq,
                "kind": kind, "payload": self._snapshot(session) if kind == "snapshot" else copy.deepcopy(payload)}

    def _emit(self, session, kind, payload=None):
        message = self._message(session, kind, payload)
        for subscriber_id, queue in list(session.subscribers.items()):
            if queue.full():
                self._stop(queue)
                del session.subscribers[subscriber_id]
            else:
                queue.put_nowait(message)
        return message

    def _advance(self, session, now):
        if session.status == "playing":
            old_sec = int(session.clock)
            session.clock = min(session.fixture.match["clip_end_sec"],
                                session.clock + max(0, now - session.updated) * session.speed)
            if session.clock >= session.fixture.match["clip_end_sec"]:
                session.status = "ended"
            if int(session.clock) != old_sec:
                while session.next_event < len(session.fixture.events):
                    event = session.fixture.events[session.next_event]
                    if event["timestamp_sec"] > int(session.clock):
                        break
                    self._emit(session, "match_event", event)
                    session.next_event += 1
                self._emit(session, "match_state", state_at(session.fixture, int(session.clock)))
            if now - session.last_snapshot >= self.settings.snapshot_interval or session.status == "ended":
                self._emit(session, "snapshot")
                session.last_snapshot = now
        session.updated = now

    def _prune(self, now):
        for key, session in list(self.sessions.items()):
            if not session.subscribers and now - session.touched >= self.settings.session_ttl:
                del self.sessions[key]
        for key, record in list(self.idempotency.items()):
            if now - record["created"] >= self.settings.idempotency_ttl:
                del self.idempotency[key]

    def _lookup(self, replay_id):
        session = self.sessions.get(replay_id)
        if session is None:
            raise ApiError(404, "NOT_FOUND", "Replay not found or expired.")
        return session

    def _cached(self, key, payload):
        if key is None:
            return None
        record = self.idempotency.get(key)
        if record:
            if record["payload"] != payload:
                raise ApiError(409, "STATE_CONFLICT", "Idempotency key was used for another request.")
            self._lookup(record["result"]["replay"]["replay_id"])
            return copy.deepcopy(record["result"])
        if len(self.idempotency) >= self.settings.max_idempotency_keys:
            raise ApiError(429, "CAPACITY_LIMIT", "Idempotency capacity is full; retry later.", True)
        return None

    def _remember(self, key, payload, result, now):
        if key is not None:
            self.idempotency[key] = {"payload": payload, "result": copy.deepcopy(result), "created": now}

    async def create(self, body, idempotency_key=None):
        async with self.lock:
            now = self.clock()
            self._prune(now)
            key = ("create", idempotency_key) if idempotency_key else None
            payload = json.dumps(body, sort_keys=True)
            cached = self._cached(key, payload)
            if cached is not None:
                return cached
            fixture = self.catalog.fixtures.get(body["match_id"])
            if fixture is None:
                raise ApiError(404, "NOT_FOUND", "Match not found.")
            if len(self.sessions) >= self.settings.max_sessions:
                raise ApiError(429, "CAPACITY_LIMIT", "All replay sessions are busy.", True)
            replay_id = "R-" + uuid.uuid4().hex
            session = Session(fixture, replay_id, body["speed"], now, now,
                              fixture.match["clip_start_sec"], last_snapshot=now)
            self.sessions[replay_id] = session
            result = self._snapshot(session)
            self._remember(key, payload, result, now)
            return result

    async def get(self, replay_id):
        async with self.lock:
            now = self.clock()
            self._prune(now)
            session = self._lookup(replay_id)
            self._advance(session, now)
            session.touched = now
            return self._snapshot(session)

    async def control(self, replay_id, body, idempotency_key=None, expected_run=None):
        async with self.lock:
            now = self.clock()
            self._prune(now)
            session = self._lookup(replay_id)
            key = ("control", replay_id, idempotency_key) if idempotency_key else None
            payload = json.dumps({"body": body, "expected_run": expected_run}, sort_keys=True)
            cached = self._cached(key, payload)
            if cached is not None:
                return cached
            if expected_run is not None and expected_run != session.run_id:
                raise ApiError(409, "STATE_CONFLICT", "The replay generation changed; reload its snapshot.")
            self._advance(session, now)
            action = body["action"]
            if action == "reset":
                session.run_id += 1
                session.clock = session.fixture.match["clip_start_sec"]
                session.status, session.next_event = "idle", 0
                session.insights.clear()
                session.traces.clear()
                for queue in session.subscribers.values():
                    while not queue.empty():
                        queue.get_nowait()
            elif action == "play":
                if session.status == "ended":
                    raise ApiError(409, "STATE_CONFLICT", "Replay ended; reset before playing again.")
                session.status = "playing"
            elif action == "pause":
                if session.status != "ended":
                    session.status = "paused"
            elif action == "set_speed":
                session.speed = body["speed"]
            else:
                raise ApiError(400, "INVALID_REQUEST", "Unsupported replay control.")
            session.updated = session.touched = session.last_snapshot = now
            self._emit(session, "snapshot")
            result = self._snapshot(session)
            self._remember(key, payload, result, now)
            return result

    async def subscribe(self, replay_id):
        async with self.lock:
            now = self.clock()
            self._prune(now)
            session = self._lookup(replay_id)
            self._advance(session, now)
            if len(session.subscribers) >= self.settings.max_subscribers:
                raise ApiError(429, "CAPACITY_LIMIT", "This replay has too many subscribers.", True)
            subscriber_id = uuid.uuid4().hex
            queue = asyncio.Queue(maxsize=self.settings.queue_size)
            session.subscribers[subscriber_id] = queue
            session.touched = now
            queue.put_nowait(self._message(session, "snapshot"))
            return subscriber_id, queue

    async def unsubscribe(self, replay_id, subscriber_id):
        async with self.lock:
            session = self.sessions.get(replay_id)
            if session is not None:
                session.subscribers.pop(subscriber_id, None)
                session.touched = self.clock()

    async def tick(self):
        async with self.lock:
            now = self.clock()
            self._prune(now)
            for session in self.sessions.values():
                self._advance(session, now)

    async def analysis_request(self, replay_id, start_sec=1500, end_sec=1650, language="en"):
        """Internal integration hook; no HTTP endpoint or model client is created."""
        async with self.lock:
            session = self._lookup(replay_id)
            self._advance(session, self.clock())
            if start_sec > end_sec or start_sec < session.fixture.match["clip_start_sec"] or end_sec > int(session.clock):
                raise ApiError(409, "STATE_CONFLICT", "Analysis must use an observed window in this clip.")
            request = {"contract_version": "2.0.0", "task_id": "TASK-" + uuid.uuid4().hex,
                       "replay_id": replay_id, "run_id": session.run_id,
                       "match_id": session.fixture.match["match_id"],
                       "window": {"start_sec": start_sec, "end_sec": end_sec},
                       "type": "high_press", "team_id": "HOME", "language": language,
                       "events": [copy.deepcopy(e) for e in session.fixture.events if start_sec <= e["timestamp_sec"] <= end_sec],
                       "metrics": window_metrics(session.fixture, start_sec, end_sec)}
            check_request(request)
            return request

    async def publish_analysis(self, request, result):
        """Accept an AI-module result only after identity, numeric and epoch checks."""
        check_result(request, result)
        async with self.lock:
            session = self.sessions.get(request["replay_id"])
            if session is None or request["match_id"] != session.fixture.match["match_id"]:
                return False
            if not can_publish(result, self._snapshot(session)["replay"]):
                return False
            insight = result["insight"]
            if any(item["insight_id"] == insight["insight_id"] for item in session.insights):
                return False
            session.insights = [*session.insights, copy.deepcopy(insight)][-20:]
            session.traces = [*session.traces, *copy.deepcopy(result["traces"])][-50:]
            for trace in result["traces"]:
                self._emit(session, "agent_status", trace)
            self._emit(session, "insight", insight)
            self._emit(session, "snapshot")
            return True

    async def run(self):
        while True:
            await asyncio.sleep(self.settings.tick_interval)
            await self.tick()

    async def close(self):
        async with self.lock:
            for session in self.sessions.values():
                for queue in session.subscribers.values():
                    self._stop(queue)
                session.subscribers.clear()
            self.sessions.clear()
            self.idempotency.clear()
