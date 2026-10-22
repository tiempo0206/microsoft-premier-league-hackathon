"""Real loopback HTTP checks using only the pinned runtime and standard library."""
import json
import socket
import threading
import time
import unittest
import urllib.error
import urllib.request

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


if __name__ == "__main__":
    unittest.main()
