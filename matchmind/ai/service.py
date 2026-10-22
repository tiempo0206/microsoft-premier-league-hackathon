"""Role C public boundary: `async def analyze(request: dict) -> dict`.

Shape, name and async signature are frozen by docs/02_contract.md. Role B imports this
and calls it inside a bounded background task; it must never block replay and must never
publish a result whose facts it cannot verify.

Guarantees:
* Always returns a contract-valid AnalysisResult for a valid AnalysisRequest.
* `status="passed"` only with a real model call, a real served model id, and code
  verification. Everything else is an honest `rule_fallback`.
* At most ONE correction round, then a bounded fallback. No retry loops.
* Every fact in an explanation is either a metric value from the request or an event id
  from the request window. The model is not trusted for either.

This module replaced the shipped offline stub, which only echoed one frozen example and
rejected every other window. That stub is why the contract still needed a general
fallback: see docs/handoff/ai.md.
"""
import time

from contracts.validation import check_request
from .config import from_env
from .fallback import rule_result
from .prompts import (ANALYST_SYSTEM, AUDITOR_SYSTEM, CORRECTION_TEMPLATE,
                      NARRATOR_SYSTEM, PROMPT_VERSION, claims_block, facts_block)
from .provider import ChatCompletionsProvider, ProviderError, ProviderTimeout
from .tools import TOOL_SCHEMAS, Toolbox
from .verify import (allowed_numbers, check_claims, check_narratives,
                     consistency_issues, insight_evidence)

TITLES = {"en": "Pressure creates chances", "zh": "前场压迫制造机会"}
# Two repair modes, both capped at one round total.
#   B (cheap): drop the claims the auditor refused and re-narrate the survivors.
#   A (costly): re-analyse, only when the code gate rejected claims outright.
# Floors are measured against deepseek-flash on a 20-event window:
# analyst ~3.3s (with one tool call), narrator ~2.4s, auditor ~3.3s.
REPAIR_NARRATION_FLOOR_SEC = 3.0
REPAIR_ANALYSIS_FLOOR_SEC = 4.5
AUDIT_NOTE_CHARS = 180


def _capture(provider, agent, payload):
    """Keep raw agent output for evaluation and debugging. Never leaves the process."""
    store = getattr(provider, "raw_outputs", None)
    if store is None:
        store = provider.raw_outputs = []
    store.append({"agent": agent, "payload": payload})


def _round(claims=None, narratives=None, issues=None, rejected=None,
           audit_issues=None, auditor_rejected=None):
    return {"claims": claims or [], "narratives": narratives, "issues": issues or [],
            "rejected": rejected or [], "audit_issues": audit_issues or [],
            "auditor_rejected": auditor_rejected or []}


def _identity(request):
    return (request.get("task_id"), request.get("replay_id"), request.get("run_id"))


def _rejected(request, code, message, retryable=False):
    task_id, replay_id, run_id = _identity(request)
    usable = (isinstance(task_id, str) and task_id
              and isinstance(replay_id, str) and replay_id
              and isinstance(run_id, int) and not isinstance(run_id, bool) and run_id >= 1)
    if not usable:
        raise ValueError("request has no usable identity; cannot build a rejected result")
    return {"task_id": task_id, "replay_id": replay_id, "run_id": run_id,
            "status": "rejected", "insight": None, "traces": [],
            "error": {"code": code, "message": message, "retryable": retryable}}


def _trace(request, agent, status, started, note):
    return {"task_id": request["task_id"], "agent": agent, "status": status,
            "duration_ms": max(0, int(round((time.monotonic() - started) * 1000))),
            "note": note}


def _audit_approved(audit):
    """Return (approved, issues, auditor_rejected_claim_ids).

    The auditor's own rejection list is carried out of here so a subsequent fallback can
    record which claims were refused, instead of silently publishing an empty list.
    """
    if not isinstance(audit, dict):
        return False, ["auditor returned a non-object"], []
    issues = []
    rejected = []
    if audit.get("approved") is not True:
        issues.append("auditor did not approve")
    for field in ("rejected_claims", "narrative_problems", "issues"):
        value = audit.get(field)
        if isinstance(value, list) and value:
            issues.extend(str(item) for item in value)
            if field == "rejected_claims":
                rejected.extend(str(item) for item in value)
    return not issues, issues, rejected


def _reason_for(error):
    if isinstance(error, ProviderTimeout):
        return "timeout"
    if isinstance(error, ProviderError) and error.kind in ("HTTP_429", "CAPACITY_LIMIT"):
        return "budget"
    return "provider"


async def _run_round(request, provider, config, deadline, traces, *, correction_issues=None):
    """One analyst -> narrator -> auditor pass.

    Returns a dict; `issues` non-empty means this pass must not be published.
    """
    facts = facts_block(request, allowed_numbers=allowed_numbers(request))
    toolbox = Toolbox(request)

    started = time.monotonic()
    traces.append(_trace(request, "analyst", "started", started, "prompt " + PROMPT_VERSION))
    user = facts
    if correction_issues:
        user = facts + "\n\n" + CORRECTION_TEMPLATE.format(
            issues="\n".join("- " + issue for issue in correction_issues),
            claims=claims_block(getattr(provider, "last_validated_claims", None) or []))
    raw_claims = await provider.complete_with_tools(
        system=ANALYST_SYSTEM, user=user, deadline=deadline, toolbox=toolbox,
        tool_schemas=TOOL_SCHEMAS, max_tool_calls=config.max_tool_calls, max_tokens=800)
    _capture(provider, "analyst", raw_claims)
    claims, rejected_ids, claim_issues = check_claims(raw_claims.get("claims"), request)
    traces.append(_trace(request, "analyst", "completed" if claims else "rejected",
                         started, "claims=%d rejected=%d tools=%s"
                         % (len(claims), len(rejected_ids), ",".join(toolbox.calls) or "none")))
    if not claims or claim_issues:
        return _round(claims, None, claim_issues, rejected_ids)

    started = time.monotonic()
    traces.append(_trace(request, "narrator", "started", started, "prompt " + PROMPT_VERSION))
    raw_narratives = await provider.complete_json(
        system=NARRATOR_SYSTEM,
        user=facts + "\n\nAPPROVED_CLAIMS:\n" + claims_block(claims),
        deadline=deadline, max_tokens=500)
    _capture(provider, "narrator", raw_narratives)
    narratives, narrative_issues = check_narratives(raw_narratives, request, claims)
    traces.append(_trace(request, "narrator", "completed" if narratives else "rejected",
                         started, "issues=%d" % len(narrative_issues)))
    if narratives is None:
        return _round(claims, None, narrative_issues, rejected_ids)

    started = time.monotonic()
    traces.append(_trace(request, "auditor", "started", started, "prompt " + PROMPT_VERSION))
    raw_audit = await provider.complete_json(
        system=AUDITOR_SYSTEM,
        user=(facts + "\n\nCLAIMS:\n" + claims_block(claims)
              + "\n\nNARRATIVES:\n" + claims_block(narratives)),
        deadline=deadline, max_tokens=500)
    _capture(provider, "auditor", raw_audit)
    approved, audit_issues, auditor_rejected = _audit_approved(raw_audit)
    note = "issues=0"
    if audit_issues:
        note = ("issues=%d rejected_claims=%d | " % (len(audit_issues), len(auditor_rejected))
                + " ; ".join(audit_issues))[:AUDIT_NOTE_CHARS]
    traces.append(_trace(request, "auditor", "completed" if approved else "rejected",
                         started, note))
    if not approved:
        return _round(claims, narratives, audit_issues, rejected_ids,
                      audit_issues, auditor_rejected)
    return _round(claims, narratives, [], rejected_ids)


async def _renarrate(request, provider, claims, deadline, traces, issues):
    """Cheap repair: keep the surviving claims, rewrite only the prose."""
    started = time.monotonic()
    traces.append(_trace(request, "narrator", "started", started,
                         "repair pass; prompt " + PROMPT_VERSION))
    facts = facts_block(request, allowed_numbers=allowed_numbers(request))
    raw = await provider.complete_json(
        system=NARRATOR_SYSTEM,
        user=(facts + "\n\nAPPROVED_CLAIMS:\n" + claims_block(claims)
              + "\n\nAUDITOR_ISSUES:\n" + "\n".join("- " + str(i) for i in issues)),
        deadline=deadline, max_tokens=500)
    _capture(provider, "narrator", raw)
    narratives, narrative_issues = check_narratives(raw, request, claims)
    traces.append(_trace(request, "narrator", "completed" if narratives else "rejected",
                         started, "repair issues=%d" % len(narrative_issues)))
    return narratives, narrative_issues


def _live_result(request, config, provider, claims, narratives):
    metrics = request["metrics"]
    return {
        "task_id": request["task_id"], "replay_id": request["replay_id"],
        "run_id": request["run_id"], "status": "passed",
        "insight": {
            "insight_id": "INS-" + request["task_id"],
            "match_id": request["match_id"],
            "window": dict(request["window"]),
            "type": request["type"],
            "team_id": request["team_id"],
            "metrics": dict(metrics),
            "evidence_event_ids": insight_evidence(claims),
            "claims": claims,
            "narratives": narratives,
            "verification": {"status": "passed", "method": "agent_and_code",
                             "rejected_claims": []},
            "generation": {"mode": "live_model", "provider": config.provider,
                           "model": provider.last_served_model or config.model},
            "display": {"title": TITLES.get(request["language"], TITLES["en"]), "priority": 1},
        },
        "traces": [],
        "error": None,
    }


def _select_orchestrator(config):
    """Return (run_round, renarrate, label).

    `framework` is opt-in and degrades to the direct path if the package is missing or
    fails to import, so a deployment without Agent Framework still starts. The label goes
    into the trace, because claiming a framework was used when it was not is exactly the
    kind of dishonesty this project is built to avoid.
    """
    if getattr(config, "orchestrator", "direct") == "framework":
        try:
            from . import agents
            return agents.run_round, agents.renarrate, "agent_framework"
        except Exception:                       # noqa: BLE001 - degrade, never crash
            return _run_round, _renarrate, "direct (framework unavailable)"
    return _run_round, _renarrate, "direct"


async def analyze(request, *, config=None, provider=None):
    """Frozen entry point: `await analyze(request)`.

    Calling it with no keyword arguments is deliberately OFFLINE. It performs no network
    access and returns an honest `rule_fallback`, even when the machine happens to hold a
    valid API key in its environment. Two reasons, both load-bearing:

    * Role B imports this function directly in its dispatch tests. A test must never make
      a billable model call because a developer's laptop happened to have a key.
    * `status="passed"` / `mode="live_model"` must be an explicit, deliberate decision
      taken at the composition root (`ai.app`), never an environment side effect.

    Live analysis requires either `config=ModelConfig(...)` or `provider=...`.
    """
    try:
        check_request(request)
    except Exception as error:
        try:
            return _rejected(request, "INVALID_REQUEST",
                             "AnalysisRequest failed contract validation: " + type(error).__name__)
        except ValueError:
            raise

    # Arithmetic gate before anything else. A model must never be asked to explain a
    # window whose own metrics contradict its own events: whatever it said would rest on
    # a number the evidence refutes.
    inconsistent = consistency_issues(request)
    if inconsistent:
        return _rejected(request, "INVALID_REQUEST",
                         "Request metrics contradict the supplied events: "
                         + "; ".join(inconsistent) + ". Refusing to explain.")

    # Default path: offline. No env read, no key, no socket.
    if config is None and provider is None:
        return rule_result(request, reason="no_model")

    config = config or from_env()
    clock = time.monotonic
    deadline = clock() + config.timeout
    traces = []

    if provider is None and not config.configured:
        return rule_result(request, reason="no_model", traces=traces)

    provider = provider or ChatCompletionsProvider(config)
    run_round, renarrate, orchestrator = _select_orchestrator(config)
    traces.append({"task_id": request["task_id"], "agent": "validator", "status": "started",
                   "duration_ms": 0, "note": "orchestrator=" + orchestrator})

    try:
        state = await run_round(request, provider, config, deadline, traces)
    except (ProviderTimeout, ProviderError) as error:
        traces.append({"task_id": request["task_id"], "agent": "validator",
                       "status": "failed", "duration_ms": 0,
                       "note": "model round 1 failed: " + type(error).__name__
                               + " (" + str(getattr(error, "kind", "?")) + ")"})
        return rule_result(request, reason=_reason_for(error), traces=traces)

    rejected_ids = list(dict.fromkeys(state["rejected"] + state["auditor_rejected"]))
    repair = None

    if state["issues"]:
        # Exactly one repair attempt, chosen by what actually failed.
        # Code gate refused claims -> the prose is not the problem, the facts are, so a
        # full re-analysis is the only honest repair. Auditor objected -> the claims that
        # survived code verification are sound, so drop the refused ones and rewrite the
        # prose for a tenth of the latency.
        code_failed = not state["claims"] or bool(state["rejected"])
        if code_failed and clock() + REPAIR_ANALYSIS_FLOOR_SEC < deadline:
            repair = "analysis"
        elif not code_failed and clock() + REPAIR_NARRATION_FLOOR_SEC < deadline:
            repair = "narration"

    if repair == "narration":
        survivors = [c for c in state["claims"]
                     if c["claim_id"] not in set(state["auditor_rejected"])]
        if not any(c["kind"] == "metric" for c in survivors):
            survivors = state["claims"]
        try:
            narratives, narrative_issues = await renarrate(
                request, provider, survivors, deadline, traces, state["issues"])
        except (ProviderTimeout, ProviderError) as error:
            narratives, narrative_issues = None, ["repair failed: " + type(error).__name__]
        if narratives is not None and not narrative_issues:
            state = _round(survivors, narratives, [], rejected_ids)
            state["repaired"] = True
        else:
            traces.append({"task_id": request["task_id"], "agent": "validator",
                           "status": "fallback", "duration_ms": 0,
                           "note": "narration repair did not pass code verification"})
    elif repair == "analysis":
        provider.last_validated_claims = state["claims"]
        try:
            again = await run_round(request, provider, config, deadline, traces,
                                    correction_issues=state["issues"])
        except (ProviderTimeout, ProviderError) as error:
            again = None
            traces.append({"task_id": request["task_id"], "agent": "validator",
                           "status": "fallback", "duration_ms": 0,
                           "note": "analysis repair failed: " + type(error).__name__})
        if again is not None and not again["issues"] and again["narratives"]:
            rejected_ids = list(dict.fromkeys(rejected_ids + again["rejected"]))
            state = again
            state["repaired"] = True

    if not state["claims"] or not state["narratives"] or state["issues"]:
        traces.append({"task_id": request["task_id"], "agent": "validator",
                       "status": "fallback", "duration_ms": 0,
                       "note": "verification did not pass; honest rule fallback"
                               + (" after one " + repair + " repair" if repair else "")})
        return rule_result(request, reason="invalid", traces=traces,
                           rejected_claims=rejected_ids)

    result = _live_result(request, config, provider, state["claims"], state["narratives"])
    if rejected_ids:
        # Be explicit on the card that a model claim was refused and removed.
        result["insight"]["verification"]["rejected_claims"] = rejected_ids
    result["traces"] = traces
    return result
