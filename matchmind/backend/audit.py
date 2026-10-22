"""Offline readiness checks for the B-owned, versioned synthetic dataset."""
import hashlib
from pathlib import Path

from contracts.validation import check_shape
from .data import Catalog, read_json
from .stats import state_at, window_metrics

ROOT = Path(__file__).resolve().parents[1]


def require(condition):
    # Readiness validation must also run with Python optimization enabled.
    if not condition:
        raise ValueError("Invalid dataset metadata")


def audit_dataset(directory: Path, catalog=None):
    directory = Path(directory)
    issues = []
    def fail(code, detail):
        issues.append({"code": code, "detail": detail})
    try:
        catalog = catalog or Catalog(directory)
    except Exception:
        return {"status": "failed", "issues": [{"code": "INVALID_FIXTURE", "detail": "Fixture shape, ordering or event relations are invalid."}], "matches": []}

    def metadata(name):
        try:
            value = read_json(directory / name)
            require(isinstance(value, dict))
            return value
        except Exception:
            fail("INVALID_METADATA", name)
            return None

    provenance, roster, expected = (metadata(name) for name in ("PROVENANCE.json", "roster.json", "expected.json"))
    summaries = []
    for fixture in catalog.fixtures.values():
        match_id = fixture.match["match_id"]
        for warning in fixture.warnings:
            fail("GOAL_RELATION", warning)
        # Verify a one-to-one scoring-shot/goal relation in both directions.
        goals = [e for e in fixture.events if e["type"] == "goal"]
        for shot in (e for e in fixture.events if e["type"] == "shot" and e["outcome"] == "goal"):
            matches = [g for g in goals if g["player_id"] == shot["player_id"] and g["team_id"] == shot["team_id"]
                       and g["possession_id"] == shot["possession_id"] and 0 <= g["timestamp_sec"] - shot["timestamp_sec"] <= 1]
            if len(matches) != 1:
                fail("SCORING_SHOT_RELATION", shot["event_id"])
        if roster is not None:
            try:
                require(isinstance(roster, dict))
                require(type(roster["version"]) is int and roster["version"] == 1 and roster["match_id"] == match_id)
                teams = roster["teams"]
                require(isinstance(teams, dict))
                require(set(teams) == {"HOME", "AWAY"})
                require(all(isinstance(team, list) and len(team) == 11 for team in teams.values()))
                players = [player for team in teams.values() for player in team]
                require(all(isinstance(player, str) and player for player in players) and len(set(players)) == 22)
                for event in fixture.events:
                    if event["player_id"] not in teams[event["team_id"]]:
                        fail("PLAYER_NOT_IN_ROSTER", event["event_id"])
            except (KeyError, TypeError, ValueError):
                fail("INVALID_ROSTER", "roster.json")
        if expected is not None:
            try:
                require(isinstance(expected, dict))
                require(type(expected["version"]) is int and expected["version"] == 1 and expected["match_id"] == match_id)
                require(len(expected["states"]) == 3 and {s["at_sec"] for s in expected["states"]} == {1500, 1650, 1800})
                for baseline in expected["states"]:
                    check_shape("MatchState", baseline)
                    if state_at(fixture, baseline["at_sec"]) != baseline:
                        fail("STATE_BASELINE_MISMATCH", str(baseline["at_sec"]))
                window = expected["window"]
                require(window == {"start_sec": 1500, "end_sec": 1650})
                check_shape("Metrics", expected["metrics"])
                if window_metrics(fixture, window["start_sec"], window["end_sec"]) != expected["metrics"]:
                    fail("METRIC_BASELINE_MISMATCH", "expected.json")
            except Exception:
                fail("INVALID_EXPECTATIONS", "expected.json")
        summaries.append({"match_id": match_id, "dataset_version": fixture.match["generator_version"],
                          "events": len(fixture.events), "synthetic": fixture.match["synthetic"]})

    if provenance is not None:
        try:
            require(isinstance(provenance, dict))
            require(provenance["kind"] == "derived_original_synthetic" and provenance["license"] == "CC0-1.0")
            require(len(summaries) == 1 and provenance["dataset_version"] == summaries[0]["dataset_version"])
            require(provenance["event_count"] == summaries[0]["events"])
            hashes = provenance["artifact_sha256"]
            require(isinstance(hashes, dict))
            require(set(hashes) == {"demo.match.json", "demo.events.jsonl", "roster.json", "expected.json"})
            for name, expected_hash in hashes.items():
                if hashlib.sha256((directory / name).read_bytes()).hexdigest() != expected_hash:
                    fail("DATA_HASH_MISMATCH", name)
            raw_rows = [row for row in (directory / "demo.events.jsonl").read_text(encoding="utf-8").splitlines() if row.strip()]
            if len(raw_rows) != provenance["event_count"]:
                fail("DUPLICATE_EVENT", "The static fixture must contain each event exactly once.")
            sources = provenance["source_sha256"]
            require(isinstance(sources, dict))
            require(provenance["source_directory"] == "data/fixtures")
            require(set(sources) == {"demo.match.json", "demo.events.jsonl", "PROVENANCE.json"})
            for name, expected_hash in sources.items():
                if hashlib.sha256((ROOT / "data/fixtures" / name).read_bytes()).hexdigest() != expected_hash:
                    fail("SOURCE_HASH_MISMATCH", name)
        except (KeyError, TypeError, ValueError, OSError):
            fail("INVALID_PROVENANCE", "PROVENANCE.json")
    return {"status": "failed" if issues else "passed", "matches": summaries, "issues": issues}
