"""Editorial policy: how many cards may air, and whether a card adds to the story.

Two problems this addresses, both borrowed from a rival's published ablation. Their
StorylineKeeper loss was "20 of 28 goals lose their match context"; their MomentScout loss
was "about 21 graphics a minute instead of 0.7". A product that shows every moment is as
broken as one that shows none, and a card that does not know what came before it cannot say
"the second time in five minutes".

Honest status: this module is a **pure, tested policy**, not yet wired into publication.
Activating it needs one contract field (`Insight.sequence` / `Insight.continues_from`) so the
frontend can render continuity without inventing it; that is a 2.1.0 item, listed in
`docs/handoff/ai.md`. It is exposed as an MCP tool so the policy can be used today by any
client that already holds the insights.

    python -m ai.storyline          # run the policy over a small synthetic sequence
"""
import json

# Match-time seconds, not wall clock: two cards about the same spell of play should not both
# air even if the replay is being scrubbed quickly.
MIN_INTERVAL_SEC = 45
# Hard ceiling so a pathological feed cannot flood the screen.
MAX_CARDS_PER_10_MIN = 8
CONTEXT_DECAY = 4          # how many earlier insights stay narratively relevant


class Storyline:
    """Admission and continuity for a single replay's insight stream."""

    def __init__(self, *, min_interval_sec=MIN_INTERVAL_SEC,
                 max_cards=MAX_CARDS_PER_10_MIN, context_decay=CONTEXT_DECAY):
        self.min_interval_sec = min_interval_sec
        self.max_cards = max_cards
        self.context_decay = context_decay
        self.admitted = []
        self.seen_keys = set()

    def _key(self, insight):
        window = insight.get("window") or {}
        return (insight.get("match_id"), insight.get("type"), insight.get("team_id"),
                window.get("start_sec"), window.get("end_sec"), insight.get("state_version"))

    def _window_end(self, insight):
        return (insight.get("window") or {}).get("end_sec", 0)

    def _window_start(self, insight):
        return (insight.get("window") or {}).get("start_sec", 0)

    def consider(self, insight):
        """Decide whether this insight may air. Returns (admit: bool, decision: dict).

        A refusal is always labelled with a machine-readable reason, so a caller can log it
        instead of silently dropping a card.

        The spacing rule compares the NEW card's window START against the previous card's
        window END, not end against end. End-to-end would let two heavily overlapping
        windows both air (1500-1650 then 1600-1700 differ by 50s at the end but describe the
        same spell of play twice), which is exactly the flood this policy exists to prevent.
        """
        if not isinstance(insight, dict):
            return False, {"reason": "NOT_AN_INSIGHT"}
        key = self._key(insight)
        if key in self.seen_keys:
            return False, {"reason": "DUPLICATE_WINDOW"}

        start = self._window_start(insight)
        for earlier in self.admitted:
            prev_end = self._window_end(earlier)
            if start < prev_end + self.min_interval_sec:
                return False, {"reason": "TOO_SOON",
                               "previous_insight_id": earlier.get("insight_id"),
                               "previous_window_end_sec": prev_end,
                               "this_window_start_sec": start,
                               "min_interval_sec": self.min_interval_sec}
        end = self._window_end(insight)
        ten_minute = self._window_end({"window": {"end_sec": end - 600}})
        recent = [i for i in self.admitted if self._window_end(i) > ten_minute]
        if len(recent) >= self.max_cards:
            return False, {"reason": "RATE_CAP",
                           "cards_in_last_10_min": len(recent),
                           "max_cards": self.max_cards}

        continuity = self._continuity(insight)
        self.seen_keys.add(key)
        self.admitted.append(insight)
        return True, {"reason": "ADMITTED", "sequence": len(self.admitted),
                      "previous_insight_id": (self.admitted[-2].get("insight_id")
                                              if len(self.admitted) > 1 else None),
                      "continuity": continuity}

    def _continuity(self, insight):
        """What this card adds over the recent ones: a repeat count and a fresher fact."""
        window = insight.get("window") or {}
        mine = {claim.get("metric_key"): claim.get("metric_value")
                for claim in (insight.get("claims") or []) if claim.get("kind") == "metric"}
        repeats = 0
        previous = None
        for earlier in self.admitted[-self.context_decay:]:
            if earlier.get("type") == insight.get("type") and \
                    earlier.get("team_id") == insight.get("team_id"):
                repeats += 1
            previous = earlier
        improved = []
        if previous:
            theirs = {claim.get("metric_key"): claim.get("metric_value")
                      for claim in (previous.get("claims") or [])
                      if claim.get("kind") == "metric"}
            for key, value in mine.items():
                if key in theirs and isinstance(value, (int, float)) \
                        and isinstance(theirs[key], (int, float)) and value != theirs[key]:
                    improved.append({"metric_key": key, "from": theirs[key], "to": value})
        return {
            "repeat_of_type_for_team": repeats,
            "is_repeat": repeats > 0,
            "changed_metrics_since_previous": improved,
            "note": ("A repeated pattern; say so rather than presenting it as new."
                     if repeats else "First occurrence of this pattern in the storyline."),
            "window": {"start_sec": window.get("start_sec"), "end_sec": window.get("end_sec")},
        }


def review(insights, **options):
    """Run the policy over a list of insights and report admissions and refusals."""
    storyline = Storyline(**options)
    decisions = []
    for insight in insights:
        admit, decision = storyline.consider(insight)
        decisions.append({"insight_id": (insight or {}).get("insight_id"),
                          "admit": admit, **decision})
    return {"admitted": len(storyline.admitted), "considered": len(insights),
            "refused": sum(1 for d in decisions if not d["admit"]),
            "decisions": decisions}


def main():
    def card(insight_id, start, end, kind="high_press", team="HOME", recoveries=3):
        return {"insight_id": insight_id, "match_id": "MM-DEMO-01", "type": kind,
                "team_id": team, "window": {"start_sec": start, "end_sec": end},
                "claims": [{"claim_id": "C1", "kind": "metric",
                            "metric_key": "high_recoveries", "metric_value": recoveries}]}

    example = [card("INS-1", 1500, 1650, recoveries=3),
               card("INS-1", 1500, 1650, recoveries=3),     # exact duplicate
               card("INS-2", 1600, 1700, recoveries=1),     # inside the interval
               card("INS-3", 1700, 1780, recoveries=4)]     # far enough apart
    print(json.dumps(review(example), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
