"""Finite synthetic regression cases; never imports the backend under test.

This is a sparse event-template generator, not a full football simulator or
model-training dataset. Expected trigger counts come from template specs;
ownership expectations use an independent per-second reference calculation.
"""
import copy
import json
from pathlib import Path
import random

VERSION = "b-scenarios-1.0"
DEVELOPMENT_SEEDS = tuple(range(1, 9))
HOLDOUT_SEEDS = tuple(range(1001, 1009))
# high recoveries, linked recoveries, observed shots by the subject team
PATTERNS = {"positive": (3, 2, 2), "late_shots": (3, 0, 3),
            "low_recovery": (0, 0, 3), "one_recovery_two_shots": (1, 1, 2),
            "cutoff_equal": (3, 3, 3), "cutoff_below": (0, 0, 3),
            "empty_window": (0, 0, 0), "censored_window": (1, 0, 0)}
FAULTS = ("outside_time", "wrong_match", "out_of_order", "conflicting_duplicate",
          "player_changes_team", "possession_changes_team", "coordinate_outside",
          "missing_pass_end", "goal_scorer_mismatch")
SOURCE = Path(__file__).resolve().parents[2] / "data/extra/validated-demo/demo.match.json"


def reference_states(match, events, seconds):
    """Reference via discrete owner lookup, independent of interval integration."""
    start, end = match["clip_start_sec"], match["clip_end_sec"]
    prefix = {team: [0] for team in ("HOME", "AWAY")}
    for sec in range(start, end):
        observed = [e for e in events if e["timestamp_sec"] <= sec]
        owner = observed[-1]["team_id"] if observed else match["initial_possession_team"]
        for team in prefix:
            prefix[team].append(prefix[team][-1] + int(owner == team))
    results = []
    for sec in seconds:
        observed = [e for e in events if e["timestamp_sec"] <= sec]
        state = {"match_id": match["match_id"], "at_sec": sec,
                 "last_event_id": observed[-1]["event_id"] if observed else None,
                 "possession_seconds": {team: prefix[team][sec-start] for team in prefix}}
        for key, kind in (("score", "goal"), ("shots", "shot"), ("passes", "pass"), ("completed_passes", "pass")):
            state[key] = {team: sum(e["team_id"] == team and e["type"] == kind
                                   and (key != "completed_passes" or e["outcome"] == "successful")
                                   for e in observed) for team in prefix}
        results.append(state)
    return results


def normal_case(seed, pattern, subject, direction, split):
    rng = random.Random(f"{VERSION}/{seed}/{pattern}")
    match = json.loads(SOURCE.read_text(encoding="utf-8"))
    identity = f"BT-{split}-{seed}-{pattern}-{subject}-{direction}"
    opponent = "AWAY" if subject == "HOME" else "HOME"
    match.update(match_id=identity, seed=seed, generator_version=VERSION,
                 initial_possession_team=opponent, home_attack_direction=direction)
    events, possession = [], 0
    current_team, current_possession = opponent, "P000"

    def point(team, normalized_x):
        right = (direction == "right") == (team == "HOME")
        return {"x": round(normalized_x if right else 100-normalized_x, 3), "y": rng.randint(25, 75)}

    def emit(second, kind, team, normalized_x=45, outcome="successful", player=None):
        nonlocal possession, current_team, current_possession
        if kind == "recovery":
            possession += 1
            current_team, current_possession = team, f"P{possession:03d}"
        if team != current_team:
            raise ValueError("Template changed team without a recorded recovery")
        player = player or ("H" if team == "HOME" else "A") + f"{rng.randint(1,11):02d}"
        event = {"event_id": f"{identity}-E{len(events)+1:03d}", "match_id": identity,
                 "timestamp_sec": second, "period": 1, "type": kind, "team_id": team,
                 "player_id": player, "possession_id": current_possession,
                 "position": point(team, normalized_x),
                 "end_position": point(team, min(98, normalized_x+4)) if kind == "pass" else None,
                 "outcome": outcome}
        events.append(event)
        return event

    initial = 1701 if pattern == "empty_window" else 1501
    emit(initial, "pass", opponent)
    emit(initial+7, "pass", opponent, outcome="failed" if seed % 2 else "successful")
    if pattern == "empty_window":
        starts = [1715]
    elif pattern == "censored_window":
        starts = [1640+rng.randint(0,3)]
    else:
        starts = [base+rng.randint(0,3) for base in (1520, 1565, 1610)]
    for index, second in enumerate(starts):
        if pattern == "one_recovery_two_shots" and index > 0:
            emit(second, "pass", opponent)
            continue
        x = 66.67 if pattern == "cutoff_equal" else 66.66 if pattern == "cutoff_below" else (
            rng.randint(40,60) if pattern == "low_recovery" else rng.randint(72,85))
        emit(second, "recovery", subject, x)
        emit(second+2, "pass", subject, min(90, x+2))
        delays = ([7,11] if pattern == "one_recovery_two_shots" else
                  [15] if pattern == "cutoff_equal" else
                  [rng.randint(16,22)] if pattern == "late_shots" else
                  [11] if pattern == "censored_window" else
                  [] if pattern == "positive" and index == 2 else [rng.randint(6,12)])
        last = second+2
        for delay in delays:
            scoring = pattern == "positive" and index == 0
            shot = emit(second+delay, "shot", subject, 90,
                        "goal" if scoring else "on_target" if seed % 2 else "off_target")
            last = second+delay
            if scoring:
                emit(last+1, "goal", subject, 98, "goal", shot["player_id"])
                last += 1
        emit(last+3, "recovery", opponent, 30)
        emit(last+5, "pass", opponent, 35)
    emit(1760, "recovery", subject, 20)
    emit(1770, "pass", subject, 25)
    events.sort(key=lambda e: (e["timestamp_sec"], e["event_id"]))
    states = reference_states(match, events, (1500,1650,1800))
    high, linked, shots = PATTERNS[pattern]
    middle = states[1]["possession_seconds"]
    metrics = {"high_recoveries": high, "linked_shots": linked, "window_seconds": 150,
               "home_possession_seconds": middle["HOME"], "away_possession_seconds": middle["AWAY"],
               "home_shots": shots if subject == "HOME" else 0,
               "away_shots": shots if subject == "AWAY" else 0}
    return {"case_id": identity, "kind": "normal", "split": split, "seed": seed,
            "pattern": pattern, "subject_team": subject, "direction": direction,
            "match": match, "events": events,
            "expected": {"states": states, "metrics": metrics, "trigger": high >= 3 and linked >= 2}}


def fault_case(base, fault):
    case = copy.deepcopy(base)
    case.update(case_id=base["case_id"]+"/fault/"+fault, kind="invalid", fault=fault)
    rows = case["events"]
    target = next(e for e in rows if e["type"] == "recovery" and e["team_id"] == case["subject_team"])
    if fault == "outside_time": rows[0]["timestamp_sec"] = 1499
    elif fault == "wrong_match": rows[0]["match_id"] = "OTHER-MATCH"
    elif fault == "out_of_order": rows[0], rows[1] = rows[1], rows[0]
    elif fault == "conflicting_duplicate":
        other = copy.deepcopy(rows[0]); other["position"]["x"] += 1; rows.append(other)
    elif fault == "player_changes_team": target["player_id"] = rows[0]["player_id"]
    elif fault == "possession_changes_team": target["possession_id"] = rows[0]["possession_id"]
    elif fault == "coordinate_outside": rows[0]["position"]["x"] = 101
    elif fault == "missing_pass_end": rows[0]["end_position"] = None
    elif fault == "goal_scorer_mismatch":
        goal = next(e for e in rows if e["type"] == "goal")
        goal["player_id"] = goal["player_id"][0] + ("02" if goal["player_id"][1:] == "01" else "01")
    else: raise ValueError("Unknown fault template")
    case["expected"] = {"rejected": True, "mechanism": "goal_relation_warning" if fault == "goal_scorer_mismatch" else "loader_error"}
    return case


def cases(development_seeds=DEVELOPMENT_SEEDS, holdout_seeds=HOLDOUT_SEEDS):
    development_seeds, holdout_seeds = tuple(development_seeds), tuple(holdout_seeds)
    if (not development_seeds or not holdout_seeds or set(development_seeds) & set(holdout_seeds)
            or len(set(development_seeds)) != len(development_seeds) or len(set(holdout_seeds)) != len(holdout_seeds)):
        raise ValueError("Development/holdout seeds must be nonempty and disjoint")
    for split, seeds in (("development", development_seeds), ("regression_holdout", holdout_seeds)):
        for seed in seeds:
            for pattern in PATTERNS:
                for team in ("HOME", "AWAY"):
                    for direction in ("right", "left"):
                        yield normal_case(seed, pattern, team, direction, split)
        for team in ("HOME", "AWAY"):
            for direction in ("right", "left"):
                base = normal_case(seeds[0], "positive", team, direction, split)
                for fault in FAULTS:
                    yield fault_case(base, fault)
