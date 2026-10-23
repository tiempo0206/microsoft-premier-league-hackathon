"""Microsoft Agent Framework orchestration (Role C, work block C4).

The verified pipeline is unchanged in shape; only the thing that executes each role is
swapped. Three `Agent` objects share one `OpenAIChatCompletionClient` pointed at the
OpenAI-compatible endpoint, each with its own instructions and its own tool binding.

Select it with `MATCHMIND_ORCHESTRATOR=framework`. The default stays `direct` so the
measured 12-window result keeps describing the shipped path; `framework` is opt-in until
it has been measured against the same harness.

Two concrete findings from wiring this, both verified with real requests:

1. `agent_framework 1.22.0` no longer exports `ChatAgent`; the class is `Agent`. Copied
   tutorials using `ChatAgent` fail on import.
2. DeepSeek enables thinking by default at effort "high". `ChatOptions` is a TypedDict and
   the OpenAI client forwards `extra_body`, so the documented top-level
   `{"thinking": {"type": "disabled"}}` reaches the provider through the framework.
   Measured on the same prompt: 1047 ms with thinking disabled, 1719 ms with it on.

This module imports the framework lazily, so a deployment without it still serves the
direct path instead of failing to start.
"""
import json
import time

from .prompts import (ANALYST_SYSTEM, AUDITOR_SYSTEM, CORRECTION_TEMPLATE,
                      NARRATOR_SYSTEM, PROMPT_VERSION, claims_block, facts_block)
from .tools import Toolbox
from .verify import allowed_numbers, check_claims, check_narratives


def _options(config, *, max_tokens):
    options = {"max_tokens": max_tokens, "response_format": {"type": "json_object"}}
    if config.thinking == "disabled":
        options["extra_body"] = {"thinking": {"type": "disabled"}}
    else:
        options["extra_body"] = {"thinking": {"type": "enabled"}}
        options["reasoning_effort"] = config.thinking
    return options


class Roles:
    """One shared client, three agents that cannot do each other's job."""

    def __init__(self, config):
        from agent_framework import Agent
        from agent_framework.openai import OpenAIChatCompletionClient

        self.config = config
        self._agent_class = Agent
        self.client = OpenAIChatCompletionClient(
            model=config.model, api_key=config.api_key, base_url=config.base_url)

    def _agent(self, name, instructions, *, max_tokens, tools=None):
        return self._agent_class(
            client=self.client, name=name, instructions=instructions, tools=tools,
            default_options=_options(self.config, max_tokens=max_tokens))

    def analyst(self, toolbox):
        # Tools are the same bounded, request-scoped callables the direct path uses.
        return self._agent("analyst", ANALYST_SYSTEM, max_tokens=800, tools=[
            toolbox.get_metrics, toolbox.get_event_window, toolbox.get_candidate_moments])

    def narrator(self):
        return self._agent("narrator", NARRATOR_SYSTEM, max_tokens=500)

    def auditor(self):
        return self._agent("auditor", AUDITOR_SYSTEM, max_tokens=500)


def _text(response):
    text = getattr(response, "text", None)
    if callable(text):
        text = text()
    if not isinstance(text, str):
        text = str(response)
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    return text


def _json(response):
    try:
        value = json.loads(_text(response))
    except ValueError:
        return None
    return value if isinstance(value, dict) else None


def _trace(request, agent, status, started, note):
    return {"task_id": request["task_id"], "agent": agent, "status": status,
            "duration_ms": max(0, int(round((time.monotonic() - started) * 1000))),
            "note": note}


def _capture(provider, agent, payload):
    store = getattr(provider, "raw_outputs", None)
    if store is None:
        store = provider.raw_outputs = []
    store.append({"agent": agent, "origin": "agent_framework", "payload": payload})


NARRATOR_RETRY_FLOOR_SEC = 3.0


async def _narrate_framework(request, provider, roles, facts, claims, deadline, traces,
                             label, prior_issues=None):
    """One narrator call through Agent Framework plus its code check."""
    started = time.monotonic()
    traces.append(_trace(request, "narrator", "started", started, label))
    prompt = facts + "\n\nAPPROVED_CLAIMS:\n" + claims_block(claims)
    if prior_issues:
        prompt += ("\n\nYOUR PREVIOUS ATTEMPT WAS REJECTED BY THE CODE CHECK:\n"
                   + "\n".join("- " + str(issue) for issue in prior_issues))
    raw = _json(await roles.narrator().run(prompt)) or {}
    _capture(provider, "narrator", raw)
    narratives, issues = check_narratives(raw, request, claims)
    traces.append(_trace(request, "narrator", "completed" if narratives else "rejected",
                         started, "%s issues=%d" % (label, len(issues))))
    return narratives, issues


async def run_round(request, provider, config, deadline, traces, *, correction_issues=None):
    """Same contract as ai.service._run_round, executed by Agent Framework agents."""
    roles = getattr(provider, "framework_roles", None)
    if roles is None:
        roles = provider.framework_roles = Roles(config)

    facts = facts_block(request, allowed_numbers=allowed_numbers(request))
    toolbox = Toolbox(request)

    started = time.monotonic()
    traces.append(_trace(request, "analyst", "started", started,
                         "agent_framework; prompt " + PROMPT_VERSION))
    prompt = facts
    if correction_issues:
        prompt = facts + "\n\n" + CORRECTION_TEMPLATE.format(
            issues="\n".join("- " + issue for issue in correction_issues),
            claims=claims_block(getattr(provider, "last_validated_claims", None) or []))
    raw_claims = _json(await roles.analyst(toolbox).run(prompt)) or {}
    _capture(provider, "analyst", raw_claims)
    claims, rejected_ids, claim_issues = check_claims(raw_claims.get("claims"), request)
    traces.append(_trace(request, "analyst", "completed" if claims else "rejected",
                         started, "framework claims=%d rejected=%d tools=%s"
                         % (len(claims), len(rejected_ids), ",".join(toolbox.calls) or "none")))
    if not claims or claim_issues:
        return {"claims": claims, "narratives": None, "issues": claim_issues,
                "rejected": rejected_ids, "audit_issues": [], "auditor_rejected": []}

    narratives, narrative_issues = await _narrate_framework(
        request, provider, roles, facts, claims, deadline, traces,
        "agent_framework; prompt " + PROMPT_VERSION)
    if narratives is None and time.monotonic() + NARRATOR_RETRY_FLOOR_SEC < deadline:
        # Same rule as the direct path: a code-check failure is not an auditor correction and
        # must not spend that budget.
        narratives, narrative_issues = await _narrate_framework(
            request, provider, roles, facts, claims, deadline, traces,
            "agent_framework; code-check retry", prior_issues=narrative_issues)
    if narratives is None:
        return {"claims": claims, "narratives": None, "issues": narrative_issues,
                "rejected": rejected_ids, "audit_issues": [], "auditor_rejected": []}

    started = time.monotonic()
    traces.append(_trace(request, "auditor", "started", started,
                         "agent_framework; prompt " + PROMPT_VERSION))
    raw_audit = _json(await roles.auditor().run(
        facts + "\n\nCLAIMS:\n" + claims_block(claims)
        + "\n\nNARRATIVES:\n" + claims_block(narratives))) or {}
    _capture(provider, "auditor", raw_audit)
    # Use the same derivation as the direct path: the decision comes from the auditor's lists, not
    # from a boolean it can contradict.
    from .service import _audit_approved
    approved, audit_issues, auditor_rejected = _audit_approved(raw_audit)
    traces.append(_trace(request, "auditor", "completed" if approved else "rejected",
                         started, "framework issues=%d" % len(audit_issues)))
    if audit_issues:
        # Same rule as the direct path: the auditor's refusals must not be reported as
        # code-gate rejections, or the cheap narration repair never runs.
        return {"claims": claims, "narratives": narratives, "issues": audit_issues,
                "rejected": rejected_ids,
                "audit_issues": audit_issues, "auditor_rejected": auditor_rejected}
    return {"claims": claims, "narratives": narratives, "issues": [],
            "rejected": rejected_ids, "audit_issues": [], "auditor_rejected": []}


async def renarrate(request, provider, claims, deadline, traces, issues):
    roles = getattr(provider, "framework_roles", None)
    if roles is None:
        roles = provider.framework_roles = Roles(provider.config)
    started = time.monotonic()
    traces.append(_trace(request, "narrator", "started", started,
                         "agent_framework repair; prompt " + PROMPT_VERSION))
    facts = facts_block(request, allowed_numbers=allowed_numbers(request))
    raw = _json(await roles.narrator().run(
        facts + "\n\nAPPROVED_CLAIMS:\n" + claims_block(claims)
        + "\n\nAUDITOR_ISSUES:\n" + "\n".join("- " + str(i) for i in issues))) or {}
    _capture(provider, "narrator", raw)
    narratives, narrative_issues = check_narratives(raw, request, claims)
    traces.append(_trace(request, "narrator", "completed" if narratives else "rejected",
                         started, "framework repair issues=%d" % len(narrative_issues)))
    return narratives, narrative_issues
