"""Qualify a synthetic fixture against the thresholds the product actually needs.

Role C cannot change Role B's fixtures, and should not: `data/generator/` and `data/fixtures/`
belong to B. What C can do is state the requirement as executable numbers instead of an
opinion, so B has a target and a regression check.

The shipped fixture is scored by this file as a **failing** example, on purpose. It is the most
useful thing this script can demonstrate.

    .\\.venv\\Scripts\\python.exe -m evaluation.fixture_qualify
    .\\.venv\\Scripts\\python.exe -m evaluation.fixture_qualify --dir data/extra/validated-demo

Where the thresholds come from:

* **Density.** A real 5-minute top-flight spell carries roughly 150-250 event records. The
  fixture has 30 in 300 seconds, i.e. one event every 10 seconds, which is why a pitch view
  looks like three dots. The threshold below is deliberately loose (1 per 3s) so it is
  achievable with a simple generator, not a simulator.
* **Detector coverage including the outcome.** A window must contain the recovery *and* the
  shot or goal it caused. The shipped 1500-1650 window contains the 1640 recovery but not the
  1680 goal, and 1650-1800 contains the goal but not the recovery, so neither card can connect
  them. This is a hard failure, not a warning.
* **Roster completeness.** An 11-a-side team needs 11 player ids or player-focused mode has
  nothing to focus on.
"""
import argparse
import json
from pathlib import Path

from ai.verify import high_press_chains
from backend.data import Catalog
from backend.stats import possession_segments, state_at, window_metrics

ROOT = Path(__file__).resolve().parents[1]

# (key, threshold, why)
THRESHOLDS = {
    "max_seconds_per_event": 3.0,
    "min_players_per_team": 11,
    "min_event_types": 4,
    "max_possession_span_sec": 60,
    "min_windows_with_outcome_linked": 1,
}

REQUIRED_TYPES = ("pass", "recovery", "shot", "goal")


def recommend_windows(directory, window_sec=150, step=10):
    """Find windows that fire the detector AND contain the outcome it wants to explain.

    This is the actionable form of PLAN_REVIEW 3.2. The shipped default is 1500-1650: it fires
    the detector, but the goal at 1680 is outside it, so no card can mention the goal. Shifting
    the same-length window to 1560-1710 fires the detector with identical metrics AND contains
    the goal, which makes the recommendation a one-line change to B's default rather than a new
    feature.
    """
    catalog = Catalog(Path(directory))
    found = []
    for match_id, fixture in sorted(catalog.fixtures.items()):
        events = list(fixture.events)
        match = fixture.match
        for start in range(match["clip_start_sec"],
                           match["clip_end_sec"] - window_sec + 1, step):
            end = start + window_sec
            for team in ("HOME", "AWAY"):
                window_events = [e for e in events if start <= e["timestamp_sec"] <= end]
                if not window_events:
                    continue
                metrics = window_metrics(fixture, start, end, team)
                fires = (metrics["high_recoveries"] >= 3 and metrics["linked_shots"] >= 2)
                if not fires:
                    continue
                chains = high_press_chains({"team_id": team, "events": window_events,
                                            "window": {"start_sec": start, "end_sec": end}})
                late = [c for c in chains if c["sustained_shots"] and not c["linked_shots"]]
                goals = [e["event_id"] for e in window_events if e["type"] == "goal"]
                found.append({
                    "match_id": match_id, "team_id": team,
                    "window": {"start_sec": start, "end_sec": end},
                    "events": len(window_events),
                    "high_recoveries": metrics["high_recoveries"],
                    "linked_shots": metrics["linked_shots"],
                    "sustained_only_chains": len(late),
                    "goals_in_window": goals,
                    "explains_an_outcome": bool(late) and bool(goals),
                })
    found.sort(key=lambda w: (not w["explains_an_outcome"], w["window"]["start_sec"]))
    return found


def summary_of_recommendations(candidates):
    explainable = [c for c in candidates if c["explains_an_outcome"]]
    return {
        "candidates_that_fire": len(candidates),
        "candidates_that_explain_an_outcome": len(explainable),
        "best": explainable[0] if explainable else None,
    }


def qualify(directory):
    catalog = Catalog(Path(directory))
    results = {"directory": str(directory), "thresholds": THRESHOLDS, "matches": []}
    for match_id, fixture in sorted(catalog.fixtures.items()):
        match = fixture.match
        events = list(fixture.events)
        span = match["clip_end_sec"] - match["clip_start_sec"]
        checks = []

        def check(key, passed, observed, required, note=""):
            checks.append({"check": key, "passed": bool(passed), "observed": observed,
                           "required": required, "note": note})

        density = round(span / max(1, len(events)), 2)
        check("seconds_per_event", density <= THRESHOLDS["max_seconds_per_event"], density,
              "<= %s" % THRESHOLDS["max_seconds_per_event"],
              "%d events over %ds" % (len(events), span))

        present = sorted({e["type"] for e in events})
        missing = [t for t in REQUIRED_TYPES if t not in present]
        check("event_types", not missing, present, "all of " + ",".join(REQUIRED_TYPES),
              "missing: " + (",".join(missing) or "none"))

        players = {}
        for event in events:
            players.setdefault(event["team_id"], set()).add(event["player_id"])
        for team in ("HOME", "AWAY"):
            count = len(players.get(team, ()))
            check("roster_" + team.lower(), count >= THRESHOLDS["min_players_per_team"],
                  count, ">= %d" % THRESHOLDS["min_players_per_team"])

        spans = [(s["end_sec"] - s["start_sec"], s["team_id"])
                 for s in possession_segments(fixture, match["clip_start_sec"],
                                              match["clip_end_sec"])]
        longest = max(spans) if spans else (0, None)
        check("longest_possession", longest[0] <= THRESHOLDS["max_possession_span_sec"],
              longest[0], "<= %d" % THRESHOLDS["max_possession_span_sec"],
              "team=%s" % (longest[1],))

        goals = [e for e in events if e["type"] == "goal"]
        scoring_shots = [e for e in events if e["type"] == "shot" and e["outcome"] == "goal"]
        final = state_at(fixture, match["clip_end_sec"])
        total_goals = final["score"]["HOME"] + final["score"]["AWAY"]
        check("goal_accounting", total_goals == len(goals) and len(goals) == len(scoring_shots),
              {"score": final["score"], "goal_events": len(goals),
               "scoring_shots": len(scoring_shots)}, "all equal")

        # The one that matters: does any window contain a recovery AND its outcome?
        linked_windows = []
        for start in range(match["clip_start_sec"], match["clip_end_sec"], 30):
            for team in ("HOME", "AWAY"):
                end = min(start + 150, match["clip_end_sec"])
                window_events = [e for e in events if start <= e["timestamp_sec"] <= end]
                if not window_events:
                    continue
                chains = high_press_chains({"team_id": team, "events": window_events,
                                            "window": {"start_sec": start, "end_sec": end}})
                if any(c["sustained_shots"] for c in chains):
                    linked_windows.append({"start_sec": start, "end_sec": end, "team": team})
        check("windows_with_outcome_linked",
              len(linked_windows) >= THRESHOLDS["min_windows_with_outcome_linked"],
              len(linked_windows),
              ">= %d" % THRESHOLDS["min_windows_with_outcome_linked"],
              "examples: %s" % (linked_windows[:3] or "none"))

        failures = [c["check"] for c in checks if not c["passed"]]
        results["matches"].append({
            "match_id": match_id, "events": len(events), "span_sec": span,
            "checks": checks, "passed": not failures, "failures": failures,
        })
    all_checks = [c for m in results["matches"] for c in m["checks"]]
    results["summary"] = {
        "matches": len(results["matches"]),
        "checks": len(all_checks),
        "failed": sum(1 for c in all_checks if not c["passed"]),
        "fixture_passes": all(m["passed"] for m in results["matches"]),
        "blocking": sorted({c["check"] for c in all_checks if not c["passed"]}),
    }
    return results


def render(results):
    lines = ["| match | check | observed | required |",
             "| --- | --- | --- | --- |"]
    for match in results["matches"]:
        for check in match["checks"]:
            mark = "" if check["passed"] else " **FAIL**"
            lines.append("| %s | %s%s | %s | %s |" % (
                match["match_id"], check["check"], mark,
                json.dumps(check["observed"]) if not isinstance(check["observed"], str)
                else check["observed"], check["required"]))
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Qualify a synthetic fixture")
    parser.add_argument("--dir", default=str(ROOT / "data" / "extra" / "validated-demo"))
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--recommend", action="store_true",
                        help="scan for windows that fire the detector AND contain an outcome")
    args = parser.parse_args(argv)

    recommendations = recommend_windows(Path(args.dir))
    if args.recommend:
        print(json.dumps({"candidates": recommendations[:12],
                          "summary": summary_of_recommendations(recommendations)},
                         ensure_ascii=False, indent=2))
        return 0

    results = qualify(Path(args.dir))
    results["recommendations"] = summary_of_recommendations(recommendations)
    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        print(render(results))
        print()
        print(json.dumps(results["summary"], ensure_ascii=False, indent=2))
        best = results["recommendations"]["best"]
        if best:
            print()
            print("Recommended demo window (fires the detector AND contains the outcome):")
            print("  %s %s %s-%s  recoveries=%d linked_shots=%d goals=%s"
                  % (best["match_id"], best["team_id"], best["window"]["start_sec"],
                     best["window"]["end_sec"], best["high_recoveries"],
                     best["linked_shots"], ",".join(best["goals_in_window"])))
    out = ROOT / ".artifacts" / "fixture-qualify"
    out.mkdir(parents=True, exist_ok=True)
    (out / "report.json").write_text(json.dumps(results, ensure_ascii=False, indent=2),
                                     encoding="utf-8")
    return 0 if results["summary"]["fixture_passes"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
