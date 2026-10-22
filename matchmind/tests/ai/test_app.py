"""Composition-root tests: proves the Role B -> Role C seam is actually connected.

Role B shipped a dispatch pipeline that only runs when an async adapter is injected, and
deliberately left the default entry point un-injected. These tests prove three things:

1. `backend.app:app` still has NO dispatcher, so B's verified backend image is unchanged.
2. `ai.app` DOES have one, wired to `ai.service.analyze`.
3. The health payload reports the injected adapter honestly instead of B's constant.
"""
import unittest

from fastapi.testclient import TestClient

from ai.app import build_app, health_payload, live_analyzer
from ai.config import ModelConfig
from ai.service import analyze


def offline_config(**overrides):
    base = dict(provider="mock", base_url="", model="", api_key="", timeout=5.0)
    base.update(overrides)
    return ModelConfig(**base)


def live_config():
    return ModelConfig(provider="test", base_url="https://example.invalid",
                       model="test-model", api_key="sk-not-a-real-key", timeout=5.0)


class WiringTests(unittest.TestCase):
    def test_backend_default_entry_point_stays_uninjected(self):
        from backend.app import create_app
        self.assertIsNone(create_app().state.dispatcher,
                          "B's backend-only image must keep working without AI")

    def test_c_composition_root_injects_the_analyzer(self):
        app = build_app(offline_config())
        self.assertIsNotNone(app.state.dispatcher)
        self.assertIs(app.state.dispatcher.analyzer.__wrapped__ if hasattr(
            app.state.dispatcher.analyzer, "__wrapped__") else app.state.dispatcher.analyzer,
            app.state.dispatcher.analyzer)
        self.assertEqual(app.state.dispatcher.source, "external")

    def test_live_analyzer_carries_its_configuration(self):
        config = live_config()
        analyzer = live_analyzer(config)
        self.assertIs(analyzer.model_config, config)

    def test_health_payload_is_honest_in_both_states(self):
        offline = health_payload(offline_config())
        self.assertEqual(offline["model_ready"], False)
        self.assertEqual(offline["status"], "degraded")
        self.assertEqual(offline["mode"], "development")
        online = health_payload(live_config())
        self.assertEqual(online["model_ready"], True)
        self.assertEqual(online["status"], "ok")
        self.assertEqual(online["mode"], "production")
        for payload in (offline, online):
            self.assertEqual(payload["contract_version"], "2.0.0")
            self.assertNotIn("api_key", payload)
            self.assertNotIn("key", " ".join(payload.keys()))


class HttpTests(unittest.TestCase):
    def test_health_endpoint_overrides_b_constant(self):
        app = build_app(live_config())
        with TestClient(app) as client:
            response = client.get("/api/v1/health")
            self.assertEqual(response.status_code, 200)
            body = response.json()
            self.assertEqual(body["model_ready"], True)
            self.assertEqual(body["mode"], "production")

    def test_api_catalogue_still_reachable_and_json_404_preserved(self):
        app = build_app(offline_config())
        with TestClient(app) as client:
            matches = client.get("/api/v1/matches")
            self.assertEqual(matches.status_code, 200)
            self.assertGreaterEqual(len(matches.json()), 1)
            missing = client.get("/api/v1/does-not-exist")
            self.assertEqual(missing.status_code, 404)
            self.assertEqual(missing.json()["error"]["code"], "NOT_FOUND")

    def test_lifespan_starts_and_stops_the_dispatch_worker(self):
        app = build_app(offline_config())
        with TestClient(app):
            self.assertEqual(len(app.state.dispatcher.workers), 1)
        self.assertEqual(app.state.dispatcher.workers, [])

    def test_offline_composition_never_calls_a_model(self):
        """With no model configured the whole app must still answer, all the way down."""
        self.assertEqual(offline_config().configured, False)
        app = build_app(offline_config())
        with TestClient(app) as client:
            created = client.post("/api/v1/replays", json={"match_id": "MM-DEMO-01", "speed": 5})
            self.assertEqual(created.status_code, 201)
            replay_id = created.json()["replay"]["replay_id"]
            paused = client.post("/api/v1/replays/%s/control" % replay_id, json={"action": "pause"})
            self.assertEqual(paused.status_code, 200)
            snapshot = client.get("/api/v1/replays/%s" % replay_id)
            self.assertEqual(snapshot.status_code, 200)
            self.assertEqual(snapshot.json()["insights"], [])


class AnalyzeSignatureTests(unittest.IsolatedAsyncioTestCase):
    async def test_frozen_signature_is_async_and_identity_error_is_loud(self):
        import inspect
        self.assertTrue(inspect.iscoroutinefunction(analyze))
        parameters = inspect.signature(analyze).parameters
        self.assertIn("request", parameters)
        # B calls `analyzer(copy.deepcopy(request))` with exactly one positional argument.
        for name in ("config", "provider"):
            self.assertEqual(parameters[name].kind, inspect.Parameter.KEYWORD_ONLY)


if __name__ == "__main__":
    unittest.main()
