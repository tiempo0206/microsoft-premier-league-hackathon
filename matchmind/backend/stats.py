"""Deterministic clip statistics. The event stream is not tracking ground truth."""
from .data import Fixture


def state_at(fixture: Fixture, at_sec: int) -> dict:
    match = fixture.match
    if not match["clip_start_sec"] <= at_sec <= match["clip_end_sec"]:
        raise ValueError("time outside clip")
    state = {"match_id": match["match_id"], "at_sec": at_sec,
             **{key: {"HOME": 0, "AWAY": 0} for key in
                ("score", "shots", "passes", "completed_passes", "possession_seconds")},
             "last_event_id": None}
    cursor, owner = match["clip_start_sec"], match["initial_possession_team"]
    for event in fixture.events:
        if event["timestamp_sec"] > at_sec:
            break
        state["possession_seconds"][owner] += event["timestamp_sec"] - cursor
        cursor, owner = event["timestamp_sec"], event["team_id"]
        kind = event["type"]
        if kind == "goal":
            state["score"][owner] += 1
        elif kind == "shot":
            state["shots"][owner] += 1
        elif kind == "pass":
            state["passes"][owner] += 1
            if event["outcome"] == "successful":
                state["completed_passes"][owner] += 1
        state["last_event_id"] = event["event_id"]
    state["possession_seconds"][owner] += at_sec - cursor
    return state


def window_metrics(fixture: Fixture, start: int, end: int, team="HOME") -> dict:
    if start > end or team not in ("HOME", "AWAY"):
        raise ValueError("invalid metric window/team")
    before, after = state_at(fixture, start), state_at(fixture, end)
    events = [e for e in fixture.events if start <= e["timestamp_sec"] <= end]
    attacks_right = (fixture.match["home_attack_direction"] == "right") == (team == "HOME")
    recoveries = [e for e in events if e["type"] == "recovery" and e["team_id"] == team
                  and (e["position"]["x"] if attacks_right else 100 - e["position"]["x"]) >= 66.67]
    linked = sum(any(s["type"] == "shot" and s["team_id"] == team
                     and s["possession_id"] == r["possession_id"]
                     and 0 < s["timestamp_sec"] - r["timestamp_sec"] <= 15
                     for s in events) for r in recoveries)
    return {"high_recoveries": len(recoveries), "linked_shots": linked, "window_seconds": end - start,
            "home_possession_seconds": after["possession_seconds"]["HOME"] - before["possession_seconds"]["HOME"],
            "away_possession_seconds": after["possession_seconds"]["AWAY"] - before["possession_seconds"]["AWAY"],
            "home_shots": sum(e["type"] == "shot" and e["team_id"] == "HOME" for e in events),
            "away_shots": sum(e["type"] == "shot" and e["team_id"] == "AWAY" for e in events)}
