"""Reproducibly prepare a corrected B-owned copy of the frozen synthetic clip.

This is a small, explicit data transformation, not a football simulator.
The shared fixture and contract are never written.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "data/fixtures"
OUTPUT = ROOT / "data/extra/validated-demo"


def canonical(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def state(at, score, shots, passes, completed, possession, last):
    return {"match_id": "MM-DEMO-01", "at_sec": at,
            **{name: {"HOME": pair[0], "AWAY": pair[1]} for name, pair in
               (("score", score), ("shots", shots), ("passes", passes),
                ("completed_passes", completed), ("possession_seconds", possession))},
            "last_event_id": last}


def contents(source=SOURCE):
    source = Path(source)
    frozen = json.loads((ROOT / "contracts/frozen.sha256.json").read_text(encoding="utf-8"))
    for name in ("demo.match.json", "demo.events.jsonl", "PROVENANCE.json"):
        if hashlib.sha256((source / name).read_bytes()).hexdigest() != frozen["data/fixtures/" + name]:
            raise ValueError("Frozen source digest changed; a shared-baseline review is required")
    match = json.loads((source / "demo.match.json").read_text(encoding="utf-8"))
    events = [json.loads(row) for row in (source / "demo.events.jsonl").read_text(encoding="utf-8").splitlines() if row.strip()]
    origin = json.loads((source / "PROVENANCE.json").read_text(encoding="utf-8"))
    by_id = {event["event_id"]: event for event in events}
    shot, goal = by_id["MM-DEMO-01-E022"], by_id["MM-DEMO-01-E023"]
    if (match["generator_version"], shot["type"], shot["player_id"], goal["type"], goal["player_id"], origin["license"]) != (
            "fixture-2.0.0", "shot", "H01", "goal", "H02", "CC0-1.0"):
        raise ValueError("Frozen source changed; review the explicit transformation before rebuilding")
    match = copy.deepcopy(match)
    match["generator_version"] = "fixture-2.0.1"
    goal["player_id"] = shot["player_id"]
    expected = {"version": 1, "match_id": match["match_id"],
                "states": [state(1500, (0, 0), (0, 0), (0, 0), (0, 0), (0, 0), None),
                           state(1650, (0, 0), (2, 0), (3, 10), (3, 7), (35, 115), "MM-DEMO-01-E020"),
                           state(1800, (1, 0), (3, 1), (5, 13), (5, 10), (110, 190), "MM-DEMO-01-E030")],
                "window": {"start_sec": 1500, "end_sec": 1650},
                "metrics": {"high_recoveries": 3, "linked_shots": 2, "window_seconds": 150,
                            "home_possession_seconds": 35, "away_possession_seconds": 115,
                            "home_shots": 2, "away_shots": 0}}
    roster = {"version": 1, "match_id": match["match_id"],
              "teams": {"HOME": [f"H{i:02d}" for i in range(1, 12)],
                        "AWAY": [f"A{i:02d}" for i in range(1, 12)]}}
    files = {"demo.match.json": canonical(match),
             "demo.events.jsonl": ("\n".join(json.dumps(e, ensure_ascii=False, sort_keys=True, separators=(",", ":")) for e in events) + "\n").encode("utf-8"),
             "expected.json": canonical(expected), "roster.json": canonical(roster)}
    provenance = {"kind": "derived_original_synthetic", "license": origin["license"],
                  "dataset_version": "fixture-2.0.1", "event_count": len(events), "seed": match["seed"],
                  "scope": origin["scope"], "authoring_method": "deterministic correction of versioned hand-authored events; no model or random generator",
                  "transformation": {"event_id": goal["event_id"], "field": "player_id", "before": "H02", "after": "H01",
                                     "reason": "The goal confirmation must name the same scorer as its scoring shot."},
                  "clock_unit": "match_seconds", "coordinates": "0..100; x right, y down; no continuous player tracking",
                  "source_directory": "data/fixtures",
                  "source_sha256": {name: hashlib.sha256((source / name).read_bytes()).hexdigest()
                                    for name in ("demo.match.json", "demo.events.jsonl", "PROVENANCE.json")},
                  "artifact_sha256": {name: hashlib.sha256(value).hexdigest() for name, value in files.items()}}
    files["PROVENANCE.json"] = canonical(provenance)
    return files


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="Read-only byte comparison against committed output")
    mode.add_argument("--write", action="store_true", help="Write only the five managed B-owned output files")
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    files = contents()
    if args.write:
        args.output.mkdir(parents=True, exist_ok=True)
        for name, value in files.items():
            (args.output / name).write_bytes(value)
    mismatches = [name for name, value in files.items()
                  if not (args.output / name).is_file() or (args.output / name).read_bytes() != value]
    print(json.dumps({"status": "failed" if mismatches else "passed", "files": len(files),
                      "mismatches": mismatches, "dataset_version": "fixture-2.0.1"}))
    return 1 if mismatches else 0


if __name__ == "__main__":
    raise SystemExit(main())
