"""A2A agent card.

The Best Multi-Agent System criterion names A2A alongside Agent Framework and MCP, and
three of the strongest rival entries ship an agent card. A card is a small, honest
description of what another agent may ask this system to do - so it is the cheapest possible
interoperability claim, provided it does not overstate the system.

Design rules:

* Every skill listed is a capability that already exists and is tested, with the same id as
  the matching MCP tool. No aspirational skills.
* `capabilities.streaming` is false because this agent answers with a complete
  `AnalysisResult`; Role B's SSE stream is a UI transport, not an A2A stream.
* `x-matchmind` is an explicitly non-standard extension block. Anything outside plain A2A
  lives there, so a strict client can ignore it safely.

    python -m ai.a2a            # print the card
"""
import json
from pathlib import Path

AGENT_CARD_SCHEMA = "https://a2a-protocol.org/schemas/v0.2.0/agent-card.json"
CARD_PATH = "/.well-known/agent-card.json"


def _skill(name, description, tags, examples):
    return {"id": name, "name": name, "description": description,
            "tags": tags, "examples": examples}


SKILLS = [
    _skill("list_matches",
           "List the synthetic matches available, with the declared clip each one covers.",
           ["catalogue", "synthetic"],
           ["Which matches can you explain?"]),
    _skill("get_metrics",
           "Return the deterministic metrics for one window. These are the only numbers an "
           "explanation may cite; they are computed from events, never by a model.",
           ["statistics", "deterministic"],
           ["Metrics for MM-DEMO-01 between 1500 and 1650 for HOME."]),
    _skill("get_event_window",
           "Return the raw synthetic events in a window, in match-clock order.",
           ["events", "synthetic"],
           ["What happened between 1560 and 1570?"]),
    _skill("get_candidate_moments",
           "Return high-recovery chains. Reports the frozen 15 second linked shot and a wider "
           "45 second context link separately, and never conflates them.",
           ["detection", "tactics"],
           ["Which recoveries turned into shots?"]),
    _skill("explain_window",
           "Run the verified explanation pipeline on one window. Returns generation.mode so a "
           "caller can tell a live model card from a deterministic rule fallback.",
           ["explanation", "verification", "multi-agent"],
           ["Explain why the 1500-1650 window mattered, in English."]),
    _skill("build_overlay",
           "Explain one window and return a timed broadcast overlay payload: lower third, "
           "stat lines and evidence pins, each labelled with its source mode.",
           ["broadcast", "overlay", "graphics"],
           ["Give me the overlay JSON for the 1500-1650 window."]),
    _skill("build_recap",
           "Summarise the whole observed prefix: score, shots, possession, goals and key "
           "links. Deterministic, and the only role that can report a goal no single moment "
           "window contains.",
           ["recap", "summary", "deterministic"],
           ["Recap the match so far between 1500 and 1800 seconds."]),
]


def agent_card(base_url="http://127.0.0.1:8000", *, version="2.0.0", model_ready=False):
    """Build the card. `model_ready` is reported truthfully rather than assumed."""
    return {
        "schemaVersion": AGENT_CARD_SCHEMA,
        "name": "MatchMind",
        "description": (
            "Verified, evidence-backed explanations of synthetic football match events. "
            "Every number comes from deterministic code and every claim cites events from "
            "the analysed window; a deterministic verifier refuses a claim it cannot trace, "
            "and the response always states whether a model was involved."),
        "url": base_url.rstrip("/") + "/a2a",
        "version": version,
        "protocolVersion": "0.2.0",
        "preferredTransport": "JSONRPC",
        "capabilities": {
            "streaming": False,
            "pushNotifications": False,
            "stateTransitionHistory": True,
        },
        "defaultInputModes": ["application/json"],
        "defaultOutputModes": ["application/json"],
        "skills": SKILLS,
        "x-matchmind": {
            "contractVersion": "2.0.0",
            "agentCardPath": CARD_PATH,
            "modelReady": bool(model_ready),
            "explanationModes": ["live_model", "rule_fallback", "precomputed"],
            "verificationMethods": ["agent_and_code", "code_only"],
            "dataProvenance": "synthetic fixtures with declared coverage; never real footage",
            "honestLimits": [
                "Clips are synthetic and short; positions are plausible, not measured.",
                "A rule_fallback card used no model. Do not describe it as live analysis.",
                "The verifier checks where a fact and a citation came from, not the meaning "
                "of a sentence; an auditor agent covers the semantic case and is not a proof.",
            ],
        },
    }


def validate_card(card):
    problems = []
    for field in ("schemaVersion", "name", "description", "url", "version",
                  "protocolVersion", "capabilities", "defaultInputModes",
                  "defaultOutputModes", "skills"):
        if field not in card:
            problems.append("missing field " + field)
    if not card.get("skills"):
        problems.append("no skills declared")
    seen = set()
    for skill in card.get("skills") or []:
        for field in ("id", "name", "description", "tags"):
            if field not in skill:
                problems.append("skill missing " + field)
        if skill.get("id") in seen:
            problems.append("duplicate skill id " + str(skill.get("id")))
        seen.add(skill.get("id"))
    if "x-matchmind" not in card:
        problems.append("missing x-matchmind honesty block")
    return problems


def write_card(directory, **kwargs):
    """Write the card where a static host or `ai.app` can serve it."""
    target = Path(directory) / ".well-known" / "agent-card.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    card = agent_card(**kwargs)
    target.write_text(json.dumps(card, ensure_ascii=False, indent=2), encoding="utf-8")
    return target


def main():
    print(json.dumps({"card": agent_card(), "problems": validate_card(agent_card())},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
