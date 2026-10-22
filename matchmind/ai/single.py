"""Deliberately weaker baseline: ONE agent does claims, prose and self-review.

This exists only so the evaluation can compare against it honestly. It is not wired into the
product and `ai.app` never uses it.

Fairness matters more than looking good. An early version of this baseline used a shorter prompt
than the product's analyst, which made the three-agent pipeline look better than it was. The prompt
below now carries the SAME rules the analyst and narrator receive: the metric definitions, the
quantifier rules, the worked example of an overreach, and the requirement to produce two audiences.
What it does NOT get is a second pair of eyes — it reviews its own output, and the deterministic
verifier still runs on whatever it produces.

Why it cannot simply be published as a passing card: frozen contract 2.0.0 requires
`verification.method == "agent_and_code"` whenever `generation.mode == "live_model"`. A single agent
reviewing its own output is not an independent check, so its result cannot legally carry status
"passed". That constraint is itself a finding of the evaluation, and this module exists to
demonstrate the difference rather than assert it.
"""
import time

from .prompts import ANALYST_SYSTEM, NARRATOR_SYSTEM, PROMPT_VERSION, claims_block, facts_block
from .verify import allowed_numbers, check_claims, check_narratives

# The rules are lifted from the product's own prompts so the comparison is about orchestration.
SINGLE_SYSTEM = (ANALYST_SYSTEM + """

You are ALSO the narrator. Produce both audiences in the same object, following this contract:
""" + NARRATOR_SYSTEM.split("Return exactly:", 1)[1] + """

You are ALSO the reviewer. Before returning, check your own claims and prose against the rules
above, and fix what is wrong. Then return ONE object with this shape:

{"claims":[...],"casual":"...","analyst":"...","self_check":"what you verified and what you changed"}""")


async def single_shot(request, *, config, provider):
    """One call. Same input, same model, same rules, same deterministic verifier as the product."""
    started = time.monotonic()
    facts = facts_block(request, allowed_numbers=allowed_numbers(request))
    calls_before = provider.calls
    raw = await provider.complete_json(system=SINGLE_SYSTEM, user=facts,
                                       deadline=time.monotonic() + config.timeout,
                                       max_tokens=1400)
    claims, rejected, claim_issues = check_claims(raw.get("claims"), request)
    narratives, narrative_issues = (
        check_narratives(raw, request, claims) if claims else (None, ["no verified claims"]))
    return {
        "mode": "single_agent",
        "prompt_version": PROMPT_VERSION,
        "elapsed_ms": round((time.monotonic() - started) * 1000),
        "model_calls": provider.calls - calls_before,
        "claims_offered": len(raw.get("claims") or []),
        "claims_accepted": len(claims),
        "claims_rejected": rejected,
        "claim_issues": claim_issues,
        "narratives_ok": narratives is not None,
        "narrative_issues": narrative_issues,
        "self_check": str(raw.get("self_check") or "")[:200],
        "raw_claims": claims_block(raw.get("claims") or []),
        "publishable_as_passed": False,
        "why_not_passed": "contract 2.0.0 requires agent_and_code for a live_model card",
        "note": NARRATOR_SYSTEM is not None,
    }
