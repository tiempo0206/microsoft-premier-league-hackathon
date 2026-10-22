"""Broadcast overlay payload.

Official rules 4.1 ask for output "timed and machine-readable enough to be rendered as
synchronized graphical overlays on a live match feed". A card rendered inside our own React
page satisfies nobody's graphics department; a timed JSON payload does.

This module is a pure serialiser over an already-verified `Insight`. It adds no facts: every
number in the payload already existed in the insight, and every event id is the one the
insight cited. It refuses to overlay an unverified insight, and it never upgrades a
`rule_fallback` into something that reads as live inference - the source mode travels with
every graphic.

    python -m ai.overlay            # print the payload for the shipped example insight

Not to be confused with the SSE transport in Role B's backend: SSE carries state changes to
our own page, this carries finished graphics to a third-party renderer.
"""
import json
from pathlib import Path

OVERLAY_SCHEMA = "matchmind.overlay/1"
# How long a lower third stays up, and how long an evidence pin lasts. Chosen so two
# consecutive cards in a 150-second window do not fight for the same second.
LOWER_THIRD_MS = 6000
PIN_MS = 3000


def _ms(window, offset_sec):
    return int(window["start_sec"] * 1000 + offset_sec * 1000)


def overlay_payload(insight, *, match_id=None, generated_at_ms=None):
    """Turn a verified Insight into timed overlay graphics.

    Raises ValueError if the insight is not publishable, because an overlay is the most
    visible thing this system can emit and an unverified one would be seen by a broadcast
    audience rather than by one engineer.
    """
    if not isinstance(insight, dict):
        raise ValueError("insight must be an object")
    window = insight.get("window") or {}
    if "start_sec" not in window or "end_sec" not in window:
        raise ValueError("insight has no window; nothing to time the graphics against")
    verification = insight.get("verification") or {}
    if verification.get("status") not in ("passed", "fallback"):
        raise ValueError("refusing to overlay an unverified insight: status=%r"
                         % (verification.get("status"),))
    generation = insight.get("generation") or {}
    if generation.get("mode") == "live_model" and verification.get("method") != "agent_and_code":
        raise ValueError("a live_model card must carry agent_and_code verification")

    source = {
        "mode": generation.get("mode"),
        "provider": generation.get("provider"),
        "model": generation.get("model"),
        "verification": verification.get("method"),
        "rejected_claims": list(verification.get("rejected_claims") or []),
    }
    graphics = []

    display = insight.get("display") or {}
    graphics.append({
        "id": insight.get("insight_id", "insight") + ":title",
        "kind": "lower_third",
        "in_ms": _ms(window, 0),
        "out_ms": _ms(window, 0) + LOWER_THIRD_MS,
        "lines": [display.get("title", "Match intelligence")],
        "source": source,
        "evidence_event_ids": list(insight.get("evidence_event_ids") or [])[:4],
    })

    # One stat line per metric claim. The value comes from the claim, which code already
    # proved equals the backend's number; nothing is recomputed here.
    for index, claim in enumerate(insight.get("claims") or []):
        if claim.get("kind") != "metric":
            continue
        graphics.append({
            "id": "%s:stat:%s" % (insight.get("insight_id", "insight"), claim.get("claim_id")),
            "kind": "stat_line",
            "in_ms": _ms(window, 0) + LOWER_THIRD_MS + index * PIN_MS,
            "out_ms": _ms(window, 0) + LOWER_THIRD_MS + (index + 1) * PIN_MS,
            "metric_key": claim.get("metric_key"),
            "metric_value": claim.get("metric_value"),
            "text": claim.get("text"),
            "source": source,
            "evidence_event_ids": list(claim.get("evidence_event_ids") or []),
        })

    # Evidence pins: where and when to highlight, so a renderer can draw without inferring.
    for event_id in (insight.get("evidence_event_ids") or [])[:8]:
        graphics.append({
            "id": "%s:pin:%s" % (insight.get("insight_id", "insight"), event_id),
            "kind": "evidence_pin",
            "event_id": event_id,
            "in_ms": _ms(window, 0),
            "out_ms": _ms(window, 0) + PIN_MS,
            "source": source,
        })

    return {
        "schema": OVERLAY_SCHEMA,
        "match_id": match_id or insight.get("match_id"),
        "insight_id": insight.get("insight_id"),
        "window": {"start_sec": window["start_sec"], "end_sec": window["end_sec"]},
        "as_of_ms": window["end_sec"] * 1000,
        "generated_at_ms": generated_at_ms,
        "synthetic": True,
        "narratives": {
            "casual": (insight.get("narratives") or {}).get("casual"),
            "analyst": (insight.get("narratives") or {}).get("analyst"),
        },
        "graphics": sorted(graphics, key=lambda g: (g["in_ms"], g["id"])),
    }


def validate_payload(payload, insight=None):
    """Cheap structural checks a renderer's CI can run before trusting a feed."""
    problems = []
    if payload.get("schema") != OVERLAY_SCHEMA:
        problems.append("schema must be " + OVERLAY_SCHEMA)
    if not payload.get("synthetic"):
        problems.append("synthetic must be true; this product never overlays real footage")
    window = payload.get("window") or {}
    if window.get("end_sec", 0) <= window.get("start_sec", 0):
        problems.append("empty window")
    graphics = payload.get("graphics") or []
    if not graphics:
        problems.append("no graphics")
    allowed_events = None
    if insight is not None:
        allowed_events = set(insight.get("evidence_event_ids") or [])
    ids = set()
    for graphic in graphics:
        gid = graphic.get("id")
        if gid in ids:
            problems.append("duplicate graphic id " + str(gid))
        ids.add(gid)
        if not graphic.get("source"):
            problems.append(str(gid) + " carries no source label")
        if graphic.get("in_ms", 0) > graphic.get("out_ms", 0):
            problems.append(str(gid) + " ends before it starts")
        if allowed_events is not None:
            for event_id in graphic.get("evidence_event_ids") or []:
                if event_id not in allowed_events:
                    problems.append(str(gid) + " cites an event the insight does not: " + event_id)
    return problems


def main():
    root = Path(__file__).resolve().parents[1]
    example = json.loads((root / "contracts/examples/analysis_result.json").read_text(encoding="utf-8"))
    payload = overlay_payload(example["insight"], generated_at_ms=0)
    print(json.dumps({"payload": payload,
                      "problems": validate_payload(payload, example["insight"])},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
