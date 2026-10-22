"""Orchestrator selection: the difference between a mock and a paid endpoint.

A default that silently routes mock-transport tests to Agent Framework once sent 13 tests
to a real DeepSeek endpoint for a minute. These tests exist so that cannot happen again.
"""
import unittest
from dataclasses import replace

import httpx

from ai.config import ModelConfig, from_env
from ai.provider import ChatCompletionsProvider
from ai.service import _select_orchestrator


def cfg(**overrides):
    base = dict(provider="test", base_url="https://example.invalid", model="m",
                api_key="sk-test", timeout=5.0, orchestrator="framework")
    base.update(overrides)
    return ModelConfig(**base)


class SelectionTests(unittest.TestCase):
    def test_an_injected_transport_forces_the_direct_path(self):
        """The caller said where traffic must go; Agent Framework would bypass it."""
        provider = ChatCompletionsProvider(
            cfg(), transport=httpx.MockTransport(lambda r: httpx.Response(200, json={})),
            use_cache=False)
        run_round, _, label = _select_orchestrator(cfg(orchestrator="framework"), provider)
        self.assertIn("injected transport", label)
        self.assertEqual(run_round.__module__, "ai.service")

    def test_a_provider_without_a_transport_honours_the_framework_setting(self):
        provider = ChatCompletionsProvider(cfg(), transport=None, use_cache=False)
        _, _, label = _select_orchestrator(cfg(orchestrator="framework"), provider)
        self.assertEqual(label, "agent_framework")

    def test_direct_is_still_selectable(self):
        provider = ChatCompletionsProvider(cfg(), transport=None, use_cache=False)
        run_round, _, label = _select_orchestrator(cfg(orchestrator="direct"), provider)
        self.assertEqual(label, "direct")
        self.assertEqual(run_round.__module__, "ai.service")

    def test_missing_framework_degrades_instead_of_crashing(self):
        """Simulate the package being absent. Setting a sys.modules entry to None makes
        `import` raise ImportError, which is what an uninstalled dependency looks like.
        Removing the entry instead would just re-import the installed package."""
        import sys
        from unittest import mock
        blocked = {"agent_framework": None, "agent_framework.openai": None,
                   "ai.agents": None}
        with mock.patch.dict(sys.modules, blocked):
            run_round, _, label = _select_orchestrator(cfg(orchestrator="framework"), None)
            self.assertTrue(label.startswith("direct"), label)
            self.assertEqual(run_round.__module__, "ai.service")

    def test_default_orchestrator_is_the_measured_one(self):
        """Whatever the default is, it must be a value the harness has measured."""
        self.assertIn(ModelConfig().orchestrator, ("framework", "direct"))
        self.assertIn(from_env(environ={}, use_env_file=False).orchestrator,
                      ("framework", "direct"))


if __name__ == "__main__":
    unittest.main()
