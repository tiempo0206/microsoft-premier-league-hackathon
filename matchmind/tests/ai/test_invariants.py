"""Cross-module invariants that no single module can enforce on its own.

Each of these has a plausible future edit that would break it silently:

* adding an eighth MCP tool and forgetting the agent card, so an A2A client cannot see a
  capability that exists;
* widening the contract's language enum and shipping a path with no template behind it;
* pasting a key into a module because "it is only for local testing".
"""
import asyncio
import re
import unittest
from pathlib import Path

from contracts.validation import check_shape

ROOT = Path(__file__).resolve().parents[2]
AI = ROOT / "ai"


class ToolCardParityTests(unittest.TestCase):
    def test_mcp_tools_and_a2a_skills_are_exactly_the_same_set(self):
        from ai import mcp_server
        from ai.a2a import agent_card

        tools = {tool.name for tool in asyncio.run(mcp_server.server.list_tools())}
        skills = {skill["id"] for skill in agent_card()["skills"]}
        self.assertEqual(tools, skills,
                         "tool(s) without a card skill: %s; skill(s) without a tool: %s"
                         % (sorted(tools - skills), sorted(skills - tools)))

    def test_every_tool_and_skill_documents_itself(self):
        from ai import mcp_server
        from ai.a2a import agent_card

        for tool in asyncio.run(mcp_server.server.list_tools()):
            self.assertTrue((tool.description or "").strip(), tool.name)
        for skill in agent_card()["skills"]:
            self.assertTrue((skill.get("description") or "").strip(), skill["id"])
            self.assertTrue(skill.get("examples"), skill["id"] + " needs an example")


class HonestySurfaceTests(unittest.TestCase):
    """Every user-visible payload must carry the mode that produced it."""

    def test_overlay_carries_a_source_mode_on_every_graphic(self):
        import json
        from ai.overlay import overlay_payload

        insight = json.loads((ROOT / "contracts/examples/analysis_result.json")
                             .read_text(encoding="utf-8"))["insight"]
        payload = overlay_payload(insight)
        for graphic in payload["graphics"]:
            self.assertIn("mode", graphic["source"])
            self.assertIn(graphic["source"]["mode"],
                          ("live_model", "rule_fallback", "precomputed"))

    def test_recap_states_its_generation_mode(self):
        from ai.recap import build_recap

        payload = build_recap("MM-DEMO-01", 1500, 1800)
        self.assertIn("mode", payload["generation"])
        self.assertEqual(payload["generation"]["mode"], "rule_fallback")
        self.assertIsNone(payload["generation"]["model"])

    def test_agent_card_states_its_honest_limits(self):
        from ai.a2a import agent_card

        limits = agent_card()["x-matchmind"]["honestLimits"]
        joined = " ".join(limits).lower()
        self.assertIn("rule_fallback", joined)
        self.assertIn("verifier checks where a fact", joined)


class ContractCouplingTests(unittest.TestCase):
    def test_language_enum_canary(self):
        """The contract allows en and zh. Fallback templates exist for exactly those two.

        If someone widens the enum, this test fails and forces them to add templates and a
        test rather than shipping a language with no prose behind it.
        """
        import json
        schema = json.loads((ROOT / "contracts/contract.schema.json").read_text(encoding="utf-8"))
        declared = set(schema["$defs"]["AnalysisRequest"]["properties"]["language"]["enum"])
        self.assertEqual(declared, {"en", "zh"},
                         "the contract language enum changed; add fallback templates, prompt "
                         "guidance and tests for the new languages before widening it")
        from ai.fallback import _TITLES
        self.assertEqual(set(_TITLES), declared)

    def test_every_metric_key_the_fallback_claims_exists_in_the_schema(self):
        import json
        schema = json.loads((ROOT / "contracts/contract.schema.json").read_text(encoding="utf-8"))
        allowed = set(schema["$defs"]["Metrics"]["properties"])
        from ai.verify import METRIC_KEYS
        self.assertEqual(set(METRIC_KEYS), allowed,
                         "ai.verify.METRIC_KEYS drifted from the frozen schema")

    def test_outcome_enum_matches_what_the_loader_accepts(self):
        """The schema and Role B's loader must agree on which event types exist.

        This started as a canary for a known gap: the frozen schema declared `foul` and Role B's
        loader refused it, so a foul event was dropped before any metric could see it. Role B has
        since closed the gap, so the assertion is now the stronger one — the two sets are equal.
        If either side drifts again this fails, and the message says which document to update with
        it, because a one-sided change here silently changes what the metrics can observe.
        """
        import ast
        import json
        schema = json.loads((ROOT / "contracts/contract.schema.json").read_text(encoding="utf-8"))
        declared = set(schema["$defs"]["Event"]["properties"]["type"]["enum"])

        # Parse Role B's whitelist with AST: a regex over the literal gets confused by the
        # nested outcome sets.
        source = (ROOT / "backend" / "data.py").read_text(encoding="utf-8")
        accepted = set()
        for node in ast.walk(ast.parse(source)):
            if (isinstance(node, ast.Assign)
                    and any(getattr(t, "id", None) == "allowed" for t in node.targets)
                    and isinstance(node.value, ast.Dict)):
                accepted = {k.value for k in node.value.keys if isinstance(k, ast.Constant)}
        self.assertTrue(accepted, "could not find Role B's allowed map")
        self.assertEqual(declared - accepted, set(),
                         "the loader refused a type the frozen schema declares; update "
                         "PLAN_REVIEW 3.1b and this test together")
        self.assertEqual(accepted - declared, set(),
                         "the loader accepts a type the frozen schema does not declare")
        self.assertIn("foul", declared,
                      "the foul gap was the case that motivated this test; if the schema dropped "
                      "foul, PLAN_REVIEW 3.1b is stale")


class NoSecretsTests(unittest.TestCase):
    def test_no_module_embeds_a_credential(self):
        pattern = re.compile(r"sk-[A-Za-z0-9]{16,}")
        offenders = []
        for path in sorted(AI.glob("*.py")):
            text = path.read_text(encoding="utf-8")
            for match in pattern.finditer(text):
                offenders.append("%s: %s..." % (path.name, match.group(0)[:6]))
        self.assertEqual(offenders, [], "a credential-looking literal is committed: %r"
                         % (offenders,))

    def test_the_config_public_view_never_exposes_the_key(self):
        from ai.config import ModelConfig

        view = ModelConfig(provider="p", base_url="https://x.invalid", model="m",
                           api_key="sk-secret-value").public()
        self.assertNotIn("sk-secret-value", str(view))
        self.assertTrue(view["key_present"])
        self.assertTrue(view["configured"])

    def test_a_plain_http_endpoint_does_not_count_as_configured(self):
        """The key must never travel over cleartext, so an http:// base url is not ready."""
        from ai.config import ModelConfig

        view = ModelConfig(provider="p", base_url="http://x.invalid", model="m",
                           api_key="sk-secret-value").public()
        self.assertFalse(view["configured"])


if __name__ == "__main__":
    unittest.main()
