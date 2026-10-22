"""A2A transport: a declared subset, tested for what it refuses as much as what it answers.

The interesting assertions are the refusals. A JSON-RPC endpoint that guesses which tool a free
sentence meant would put an untraceable step in front of every answer, which is the opposite of
this project's argument, so free text must fail loudly rather than be interpreted.
"""
import json
import unittest

from fastapi.testclient import TestClient

from ai.a2a_transport import (EXPOSED_SKILLS, SUPPORTED_METHODS, capabilities, dispatch)
from ai.app import build_app
from ai.config import ModelConfig


def offline_config():
    return ModelConfig(provider="mock", base_url="", model="", api_key="", timeout=5.0)


def request(skill, arguments=None, request_id="1", method="message/send", parts=None):
    message = {"role": "user",
               "parts": parts if parts is not None else
               [{"kind": "data", "data": {"skill": skill, "arguments": arguments or {}}}]}
    return {"jsonrpc": "2.0", "id": request_id, "method": method, "params": {"message": message}}


class DispatchTests(unittest.TestCase):
    def test_a_known_skill_answers_with_data_and_text_parts(self):
        response = dispatch(request("get_metrics", {"match_id": "MM-DEMO-01",
                                                    "start_sec": 1500, "end_sec": 1650,
                                                    "team_id": "HOME"}))
        self.assertIn("result", response)
        parts = response["result"]["parts"]
        kinds = [p["kind"] for p in parts]
        self.assertEqual(kinds, ["data", "text"])
        self.assertEqual(parts[0]["data"]["result"]["metrics"]["high_recoveries"], 3)
        self.assertIn("high_recoveries", parts[1]["text"])

    def test_an_unsupported_method_is_refused_with_the_supported_list(self):
        response = dispatch({"jsonrpc": "2.0", "id": "2", "method": "tasks/get",
                             "params": {"id": "t"}})
        self.assertEqual(response["error"]["code"], -32601)
        self.assertEqual(response["error"]["data"]["supportedMethods"],
                         list(SUPPORTED_METHODS))

    def test_free_text_is_refused_and_says_why(self):
        response = dispatch(request(None, parts=[{"kind": "text", "text": "why did they score"}]))
        self.assertEqual(response["error"]["code"], -32602)
        self.assertIn("free-text intent parsing is not implemented on purpose",
                      response["error"]["message"])

    def test_an_unexposed_skill_is_refused_even_if_it_exists_on_the_server(self):
        response = dispatch(request("server", {}))
        self.assertEqual(response["error"]["code"], -32602)
        self.assertEqual(response["error"]["data"]["exposedSkills"], list(EXPOSED_SKILLS))

    def test_bad_arguments_are_refused_not_ignored(self):
        response = dispatch(request("get_metrics", {"match_id": "MM-DEMO-01",
                                                    "start_sec": 99999, "end_sec": 99999}))
        self.assertEqual(response["error"]["code"], -32602)
        self.assertIn("window", response["error"]["message"].lower())

    def test_malformed_envelopes_are_refused(self):
        self.assertEqual(dispatch("not-an-object")["error"]["code"], -32600)
        self.assertEqual(dispatch({"jsonrpc": "1.0", "id": 1, "method": "message/send"})
                         ["error"]["code"], -32600)
        self.assertEqual(dispatch({"jsonrpc": "2.0", "id": 1, "method": "message/send",
                                   "params": {"message": {"role": "agent"}}})
                         ["error"]["code"], -32602)

    def test_the_agent_role_message_is_refused(self):
        response = dispatch({"jsonrpc": "2.0", "id": 3, "method": "message/send",
                             "params": {"message": {"role": "agent", "parts": [
                                 {"kind": "data", "data": {"skill": "list_matches"}}]}}})
        self.assertEqual(response["error"]["code"], -32602)

    def test_async_skills_are_awaited(self):
        response = dispatch(request("build_recap", {"match_id": "MM-DEMO-01",
                                                    "start_sec": 1500, "end_sec": 1800}))
        self.assertIn("result", response, response)
        data = response["result"]["parts"][0]["data"]["result"]
        self.assertEqual(data["schema"], "matchmind.recap/1")

    def test_threat_ranking_refusal_is_a_successful_answer_not_an_error(self):
        """A refusal with a reason is the product working, so it must not surface as a fault."""
        response = dispatch(request("get_threat_ranking", {"match_id": "MM-DEMO-01",
                                                           "start_sec": 1500, "end_sec": 1800}))
        self.assertIn("result", response)
        data = response["result"]["parts"][0]["data"]["result"]
        self.assertFalse(data["available"])
        self.assertIn("too short", data["reason"])

    def test_the_capability_statement_matches_the_implementation(self):
        caps = capabilities()
        self.assertEqual(caps["supportedMethods"], list(SUPPORTED_METHODS))
        self.assertFalse(caps["streaming"])
        self.assertFalse(caps["taskLifecycle"])
        self.assertFalse(caps["freeTextIntentParsing"])
        self.assertEqual(caps["exposedSkills"], list(EXPOSED_SKILLS))


class HttpTests(unittest.TestCase):
    def test_post_a2a_answers_and_reports_bad_requests(self):
        app = build_app(offline_config())
        with TestClient(app) as client:
            good = client.post("/a2a", json=request("list_matches"))
            self.assertEqual(good.status_code, 200)
            self.assertIn("result", good.json())

            bad = client.post("/a2a", json={"jsonrpc": "2.0", "id": 9, "method": "tasks/get"})
            self.assertEqual(bad.status_code, 400)
            self.assertEqual(bad.json()["error"]["code"], -32601)

            rubbish = client.post("/a2a", content=b"not json",
                                  headers={"content-type": "application/json"})
            self.assertEqual(rubbish.status_code, 400)
            self.assertEqual(rubbish.json()["error"]["code"], -32600)

    def test_the_agent_card_advertises_the_real_transport(self):
        app = build_app(offline_config())
        with TestClient(app) as client:
            card = client.get("/.well-known/agent-card.json").json()
            transport = card["x-matchmind"]["a2aTransport"]
            self.assertEqual(transport["supportedMethods"], ["message/send"])
            self.assertEqual(card["x-matchmind"]["a2aEndpoint"], "/a2a")
            limits = " ".join(card["x-matchmind"]["honestLimits"]).lower()
            self.assertIn("no streaming", limits)

    def test_the_card_skills_and_the_exposed_skills_agree(self):
        from ai.a2a import agent_card
        skills = {s["id"] for s in agent_card()["skills"]}
        self.assertEqual(skills, set(EXPOSED_SKILLS))


if __name__ == "__main__":
    unittest.main()
