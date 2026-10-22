"""Deterministic clip statistics. The event stream is not tracking ground truth."""
from .data import Fixture


def state_at(fixture: Fixture, at_sec: int) -> dict:
    match = fixture.match
    if type(at_sec) is not int or not match["clip_start_sec"] <= at_sec <= match["clip_end_sec"]:
        raise ValueError("time outside clip")
    state = {"match_id": match["match_id"], "at_sec": at_sec,
             **{key: {"HOME": 0, "AWAY": 0} for key in
                ("score", "shots", "passes", "completed_passes", "possession_seconds")},
             "last_event_id": None}
    for event in fixture.events:
        if event["timestamp_sec"] > at_sec:
            break
        owner = event["team_id"]
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
    for segment in possession_segments(fixture, match["clip_start_sec"], at_sec):
        state["possession_seconds"][segment["team_id"]] += segment["end_sec"] - segment["start_sec"]
    return state


def window_events(fixture: Fixture, start: int, end: int):
    if (type(start) is not int or type(end) is not int
            or not fixture.match["clip_start_sec"] <= start <= end <= fixture.match["clip_end_sec"]):
        raise ValueError("invalid event window")
    return [e for e in fixture.events if start <= e["timestamp_sec"] <= end]


def possession_segments(fixture: Fixture, start: int, end: int) -> list:
    """Half-open synthetic ownership intervals, carrying their recorded source."""
    window_events(fixture, start, end)  # Validate the requested logical window.
    owner, source, cursor = fixture.match["initial_possession_team"], None, start
    segments = []
    for event in fixture.events:
        second = event["timestamp_sec"]
        if second > end:
            break
        if event["type"] == "foul":
            continue  # Actor attribution does not announce a new possession owner.
        if second > cursor:
            segments.append({"start_sec": cursor, "end_sec": second,
                             "team_id": owner, "source_event_id": source})
            cursor = second
        owner, source = event["team_id"], event["event_id"]
    if cursor < end:
        segments.append({"start_sec": cursor, "end_sec": end,
                         "team_id": owner, "source_event_id": source})
    return segments


def recovery_chains(fixture: Fixture, start: int, end: int, team="HOME") -> list:
    """Event evidence for the frozen heuristic; no tracking or causal inference."""
    if team not in ("HOME", "AWAY"):
        raise ValueError("invalid metric window/team")
    events = window_events(fixture, start, end)
    attacks_right = (fixture.match["home_attack_direction"] == "right") == (team == "HOME")
    chains = []
    for recovery in events:
        if recovery["type"] != "recovery" or recovery["team_id"] != team:
            continue
        x = recovery["position"]["x"] if attacks_right else 100 - recovery["position"]["x"]
        if x < 66.67:
            continue
        following = [e for e in events if e["team_id"] == team
                     and e["possession_id"] == recovery["possession_id"]
                     and 0 < e["timestamp_sec"] - recovery["timestamp_sec"] <= 15]
        shots = [{"event_id": e["event_id"], "timestamp_sec": e["timestamp_sec"],
                  "delay_sec": e["timestamp_sec"] - recovery["timestamp_sec"]}
                 for e in following if e["type"] == "shot"]
        chains.append({"recovery_event_id": recovery["event_id"],
                       "timestamp_sec": recovery["timestamp_sec"],
                       "possession_id": recovery["possession_id"], "attack_normalized_x": x,
                       "evidence_event_ids": [recovery["event_id"], *[e["event_id"] for e in following]],
                       "linked_shots": shots})
    return chains


def high_press_detected(metrics):
    return metrics["high_recoveries"] >= 3 and metrics["linked_shots"] >= 2


def window_metrics(fixture: Fixture, start: int, end: int, team="HOME") -> dict:
    events = window_events(fixture, start, end)
    before, after = state_at(fixture, start), state_at(fixture, end)
    chains = recovery_chains(fixture, start, end, team)
    return {"high_recoveries": len(chains), "linked_shots": sum(bool(c["linked_shots"]) for c in chains),
            "window_seconds": end - start,
            "home_possession_seconds": after["possession_seconds"]["HOME"] - before["possession_seconds"]["HOME"],
            "away_possession_seconds": after["possession_seconds"]["AWAY"] - before["possession_seconds"]["AWAY"],
            "home_shots": sum(e["type"] == "shot" and e["team_id"] == "HOME" for e in events),
            "away_shots": sum(e["type"] == "shot" and e["team_id"] == "AWAY" for e in events)}
