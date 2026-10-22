"""Real loopback HTTP checks using only the pinned runtime and standard library."""
import json
import socket
import threading
import time
import unittest
import urllib.error
import urllib.request
import uuid

import uvicorn
from backend.app import create_app
from contracts.validation import check_shape


class APITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.sock = socket.socket()
        cls.sock.bind(("127.0.0.1", 0))
        cls.sock.listen(128)
        cls.base = f"http://127.0.0.1:{cls.sock.getsockname()[1]}"
        cls.server = uvicorn.Server(uvicorn.Config(cls.app, log_level="error", timeout_graceful_shutdown=2))
        cls.thread = threading.Thread(target=cls.server.run, kwargs={"sockets": [cls.sock]}, daemon=True)
        cls.thread.start()
        deadline = time.monotonic() + 10
        while not cls.server.started:
            if not cls.thread.is_alive() or time.monotonic() >= deadline:
                raise RuntimeError("Loopback API failed to start")
            time.sleep(0.01)

    @classmethod
    def tearDownClass(cls):
        cls.server.should_exit = True
        cls.thread.join(5)
        cls.sock.close()
        if cls.thread.is_alive():
            raise RuntimeError("Loopback API did not stop")

    def call(self, path, method="GET", value=None, headers=None, raw=None):
        hdr = dict(headers or {})
        if value is not None:
            raw = json.dumps(value).encode()
            hdr.setdefault("Content-Type", "application/json")
        request = urllib.request.Request(self.base + path, data=raw, method=method, headers=hdr)
        try:
            response = urllib.request.urlopen(request, timeout=3)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            return response.status, json.loads(response.read()), response.headers

    def test_health_has_no_model_requirement(self):
        status, body, headers = self.call("/api/v1/health")
        self.assertEqual(status, 200)
        check_shape("Health", body)
        self.assertFalse(body["model_ready"])
        self.assertEqual(headers["Cache-Control"], "no-store")

    def test_default_process_is_api_only_and_uses_validated_data(self):
        status, body, headers = self.call("/")
        self.assertEqual(status, 404)
        self.assertEqual(body["error"]["code"], "NOT_FOUND")
        self.assertIn("application/json", headers["Content-Type"])
        status, matches, _ = self.call("/api/v1/matches")
        self.assertEqual(status, 200)
        self.assertEqual(matches[0]["generator_version"], "fixture-2.0.1")

    def test_match_events_and_stats_use_frozen_shapes(self):
        status, matches, _ = self.call("/api/v1/matches")
        self.assertEqual(status, 200)
        self.assertEqual(len(matches), 1)
        check_shape("Match", matches[0])
        status, events, _ = self.call("/api/v1/matches/MM-DEMO-01/events?from_sec=1560&to_sec=1567")
        self.assertEqual([e["timestamp_sec"] for e in events], [1560, 1563, 1567])
        for event in events:
            check_shape("Event", event)
        status, stats, _ = self.call("/api/v1/matches/MM-DEMO-01/stats?at_sec=1650")
        check_shape("MatchState", stats)
        self.assertEqual(stats["possession_seconds"], {"HOME": 35, "AWAY": 115})

    def test_bad_query_and_unknown_resources_are_json_errors(self):
        for path, expected in [
            ("/api/v1/matches/missing", 404),
            ("/api/v1/not-a-route", 404),
            ("/api/v1/matches/MM-DEMO-01/stats?at_sec=1499", 400),
            ("/api/v1/matches/MM-DEMO-01/stats?at_sec=1650.5", 400),
            ("/api/v1/matches/MM-DEMO-01/events?from_sec=1700&to_sec=1600", 400),
        ]:
            with self.subTest(path=path):
                status, body, _ = self.call(path)
                self.assertEqual(status, expected)
                check_shape("ErrorResponse", body)

    def test_replay_create_control_and_idempotent_reset(self):
        create_key = str(uuid.uuid4())
        status, snapshot, _ = self.call("/api/v1/replays", "POST", {"match_id": "MM-DEMO-01", "speed": 5},
                                        {"Idempotency-Key": create_key})
        self.assertEqual(status, 201)
        check_shape("ReplaySnapshot", snapshot)
        rid = snapshot["replay"]["replay_id"]
        status, duplicate, _ = self.call("/api/v1/replays", "POST", {"match_id": "MM-DEMO-01", "speed": 5},
                                         {"Idempotency-Key": create_key})
        self.assertEqual(duplicate, snapshot)
        key = {"Idempotency-Key": str(uuid.uuid4()), "X-MatchMind-Expected-Run": "1"}
        status, reset, _ = self.call(f"/api/v1/replays/{rid}/control", "POST", {"action": "reset"}, key)
        status, retried, _ = self.call(f"/api/v1/replays/{rid}/control", "POST", {"action": "reset"}, key)
        self.assertEqual(reset, retried)
        self.assertEqual(reset["replay"]["run_id"], 2)
        status, error, _ = self.call(f"/api/v1/replays/{rid}/control", "POST", {"action": "play"},
                                    {"X-MatchMind-Expected-Run": "1"})
        self.assertEqual(status, 409)
        check_shape("ErrorResponse", error)

    def test_sse_begins_with_snapshot_even_with_last_event_id(self):
        _, snap, _ = self.call("/api/v1/replays", "POST", {"match_id": "MM-DEMO-01", "speed": 5})
        rid = snap["replay"]["replay_id"]
        request = urllib.request.Request(self.base + f"/api/v1/replays/{rid}/stream",
                                         headers={"Last-Event-ID": f"{rid}:1:999"})
        with urllib.request.urlopen(request, timeout=3) as response:
            lines = []
            while True:
                line = response.readline().decode().strip()
                if not line:
                    break
                lines.append(line)
            body = json.loads(next(line[6:] for line in lines if line.startswith("data: ")))
            check_shape("StreamMessage", body)
            self.assertEqual(body["kind"], "snapshot")
            self.assertEqual(body["replay_id"], rid)
            self.assertEqual(response.headers["X-Accel-Buffering"], "no")
        deadline = time.monotonic() + 2
        while self.app.state.replays.sessions[rid].subscribers and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertEqual(len(self.app.state.replays.sessions[rid].subscribers), 0)

    def test_invalid_json_body_size_and_media_are_rejected(self):
        for raw, headers, expected in [
            (b'{"match_id":', {"Content-Type": "application/json"}, 400),
            (b"x" * 17000, {"Content-Type": "application/json"}, 413),
            (b"{}", {"Content-Type": "text/plain"}, 415),
            (b'{"match_id":"MM-DEMO-01","speed":5,"extra":1}', {"Content-Type": "application/json"}, 400),
            (b'{"match_id":"MM-DEMO-01","speed":true}', {"Content-Type": "application/json"}, 400),
        ]:
            with self.subTest(expected=expected):
                status, body, _ = self.call("/api/v1/replays", "POST", headers=headers, raw=raw)
                self.assertEqual(status, expected)
                check_shape("ErrorResponse", body)


if __name__ == "__main__":
    unittest.main()
