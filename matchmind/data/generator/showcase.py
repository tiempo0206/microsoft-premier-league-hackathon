"""Small original possession scripts, not a learned football simulator.

No imports from backend or C. Independent reference states are generated from
the authored ownership schedule and action ledger. Frozen fixtures stay intact.
"""
import argparse
import hashlib
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "data/extra/showcase"
VERSION = "b-showcase-1.0"
SEED = 20261023
SCENARIOS = ("press", "delayed", "quiet")
PRESS_SPELLS = {1, 3, 5}


def canonical(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2,
                       allow_nan=False) + "\n").encode("utf-8")


def generate(scenario, seed=SEED):
    if scenario not in SCENARIOS or type(seed) is not int or not 0 <= seed <= 2**32 - 1:
        raise ValueError("Unsupported showcase scenario or seed")
    rng = random.Random(seed)
    match_id = "MM-SHOW-" + scenario.upper()
    match = {"match_id": match_id, "home": "Harbor FC", "away": "Mountain United",
             "synthetic": True, "clip_start_sec": 1500, "clip_end_sec": 1800,
             "period": 1, "home_attack_direction": "right", "initial_possession_team": "AWAY",
             "seed": seed, "generator_version": VERSION}
    events, ownership = [], [(1500, "AWAY")]
    player_cursor = {"HOME": 0, "AWAY": 0}
    for spell in range(15):
        start = 1500 + spell * 20
        team = "AWAY" if spell % 2 == 0 else "HOME"
        press = spell in PRESS_SPELLS and scenario != "quiet"
        possession = f"{match_id}-P{spell:02d}"
        x, y = (74.0 if press else 24.0), round(rng.uniform(35, 65), 1)
        ownership.append((start + 1, team))

        def add(offset, kind, outcome, endpoint=None):
            player_cursor[team] += 1
            player = ("H" if team == "HOME" else "A") + f"{(player_cursor[team]-1)%11+1:02d}"
            # A goal confirmation names the scorer of its immediately preceding shot.
            if kind == "goal":
                player = events[-1]["player_id"]
            def point(px, py):
                return {"x": round(px if team == "HOME" else 100-px, 1), "y": round(py, 1)}
            events.append({"event_id": f"{match_id}-E{len(events)+1:03d}", "match_id": match_id,
                           "timestamp_sec": start + offset, "period": 1, "type": kind,
                           "team_id": team, "player_id": player, "position": point(x, y),
                           "end_position": point(*endpoint) if endpoint else None,
                           "outcome": outcome, "possession_id": possession})

        add(1, "recovery", "successful")
        # In the scoring/press chains, stop passing before the shot. Other chains
        # have eight connected passes; each endpoint is the next recorded start.
        offsets = (3, 5, 7, 9) if press else (3, 5, 7, 9, 11, 13, 15, 17)
        for offset in offsets:
            next_point = min(94.0, x + rng.uniform(1, 3)), min(85.0, max(15.0, y + rng.uniform(-5, 5)))
            failed = not press and spell % 3 == 0 and offset == offsets[-1]
            add(offset, "pass", "failed" if failed else "successful", next_point)
            x, y = round(next_point[0], 1), round(next_point[1], 1)
        if press and spell != 5:
            scoring = scenario == "press" and spell == 3
            shot_offset = 12 if scenario == "press" else 18  # 11s linked versus 17s unlinked
            add(shot_offset, "shot", "goal" if scoring else "off_target")
            if scoring:
                add(shot_offset + 1, "goal", "goal")
        elif not press and spell % 4 == 0 and spell % 3 != 0:
            add(19, "shot", "off_target")
    return match, events, ownership


def reference_state(match, events, ownership, at):
    """Deliberately slow independent second-by-second ownership reference."""
    state = {"match_id": match["match_id"], "at_sec": at,
             **{k: {"HOME": 0, "AWAY": 0} for k in
                ("score", "shots", "passes", "completed_passes", "possession_seconds")},
             "last_event_id": None}
    for second in range(1500, at):
        owner = [team for time, team in ownership if time <= second][-1]
        state["possession_seconds"][owner] += 1
    rows = [e for e in events if e["timestamp_sec"] <= at]
    for team in ("HOME", "AWAY"):
        team_rows = [e for e in rows if e["team_id"] == team]
        state["score"][team] = len([e for e in team_rows if e["type"] == "goal"])
        state["shots"][team] = len([e for e in team_rows if e["type"] == "shot"])
        state["passes"][team] = len([e for e in team_rows if e["type"] == "pass"])
        state["completed_passes"][team] = len([e for e in team_rows if e["type"] == "pass"
                                               and e["outcome"] == "successful"])
    state["last_event_id"] = rows[-1]["event_id"] if rows else None
    return state


def contents(scenario, seed=SEED):
    match, events, ownership = generate(scenario, seed)
    states = [reference_state(match, events, ownership, at) for at in (1500, 1650, 1800)]
    # Expectations follow the authored spells, not the detector being tested.
    high, linked = {"press": (3, 2), "delayed": (3, 0), "quiet": (0, 0)}[scenario]
    window_rows = [e for e in events if 1500 <= e["timestamp_sec"] <= 1650]
    metrics = {"high_recoveries": high, "linked_shots": linked, "window_seconds": 150,
               "home_possession_seconds": states[1]["possession_seconds"]["HOME"],
               "away_possession_seconds": states[1]["possession_seconds"]["AWAY"],
               **{team.lower()+"_shots": len([e for e in window_rows
                                               if e["team_id"] == team and e["type"] == "shot"])
                  for team in ("HOME", "AWAY")}}
    expected = {"version": 1, "match_id": match["match_id"], "states": states,
                "window": {"start_sec": 1500, "end_sec": 1650}, "metrics": metrics}
    roster = {"version": 1, "match_id": match["match_id"], "teams": {
        team: [("H" if team == "HOME" else "A")+f"{i:02d}" for i in range(1, 12)]
        for team in ("HOME", "AWAY")}}
    files = {"demo.match.json": canonical(match), "roster.json": canonical(roster),
             "expected.json": canonical(expected), "demo.events.jsonl": (
                 "\n".join(json.dumps(e, sort_keys=True, separators=(",", ":")) for e in events)+"\n").encode()}
    manifest = {"kind": "original_scripted_synthetic", "license": "CC0-1.0",
                "dataset_version": VERSION, "event_count": len(events), "seed": seed,
                "scenario": scenario, "generator": "data/generator/showcase.py",
                "scope": "Original fictional 25:00-30:00 excerpt; no league data or footage.",
                "authoring_method": "Seeded possession scripts, connected pass coordinates, authored trigger/control cases.",
                "clock_unit": "match_seconds", "coordinates": "0..100; x right, y down; no tracking",
                "limitations": ["Scripted event data, not calibrated against real matches.",
                                "Pass outcomes are authored controls, not representative pass-accuracy data.",
                                "No off-ball tracking, learned xG, player speed or causal tactical labels.",
                                "Eleven roster members and event participation do not imply simultaneous tracking."],
                "design_reference": "Role C dense-fixture proposal: increase event density and retain provenance; independent B implementation.",
                "artifact_sha256": {name: hashlib.sha256(value).hexdigest() for name, value in files.items()}}
    files["PROVENANCE.json"] = canonical(manifest)
    return files


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()
    mismatches = []
    for scenario in SCENARIOS:
        directory = OUTPUT / scenario
        if args.write:
            directory.mkdir(parents=True, exist_ok=True)
        for name, value in contents(scenario).items():
            path = directory / name
            if args.write:
                path.write_bytes(value)
            if not path.is_file() or path.read_bytes() != value:
                mismatches.append(f"{scenario}/{name}")
    print(json.dumps({"status": "failed" if mismatches else "passed", "version": VERSION,
                      "scenarios": len(SCENARIOS), "mismatches": mismatches, "model_calls": 0}))
    return int(bool(mismatches))


if __name__ == "__main__":
    raise SystemExit(main())
