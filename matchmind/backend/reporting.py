"""Reproducible B engineering analysis, never an AI Insight or model output."""
import argparse
import hashlib
import json
from pathlib import Path

from .audit import ROOT, audit_dataset
from .data import Catalog
from .inputs import analysis_input
from .stats import high_press_detected, possession_segments, recovery_chains, state_at, window_metrics

DEFAULT_DATA = ROOT / "data/extra/validated-demo"
INPUT_FILES = ("demo.match.json", "demo.events.jsonl", "roster.json", "expected.json", "PROVENANCE.json")
LIMITATIONS = [
    "Original synthetic 25:00–30:00 excerpt; not a full match, official league data or live feed.",
    "Sparse event coordinates are not continuous player/ball tracking; no speed, distance or xG is inferred.",
    "Possession time uses recorded ownership on half-open intervals; it is not official measured possession.",
    "Recovery-to-shot association is a fixed event heuristic, not proof of tactical pressure or causation.",
    "This is deterministic backend analysis. No AI narratives, semantic audit or live-model result is included.",
]


def canonical(value):
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n"


def window_analysis(fixture, start, end, team):
    metrics = window_metrics(fixture, start, end, team)
    return {"window": {"start_sec": start, "end_sec": end}, "team_id": team,
            "metrics": metrics, "heuristic_eligible": high_press_detected(metrics),
            "recovery_chains": recovery_chains(fixture, start, end, team),
            "possession_segments": possession_segments(fixture, start, end)}


def check_invariants(fixture):
    start, end = fixture.match["clip_start_sec"], fixture.match["clip_end_sec"]
    previous = None
    for sec in range(start, end + 1):
        state = state_at(fixture, sec)
        if sum(state["possession_seconds"].values()) != sec - start:
            raise ValueError("Possession conservation failed")
        for team in ("HOME", "AWAY"):
            if not 0 <= state["completed_passes"][team] <= state["passes"][team]:
                raise ValueError("Pass-count invariant failed")
            if not 0 <= state["score"][team] <= state["shots"][team]:
                raise ValueError("Goal/shot invariant failed")
            for key in ("score", "shots", "passes", "completed_passes", "possession_seconds"):
                if type(state[key][team]) is not int or state[key][team] < 0:
                    raise ValueError("Nonnegative integer-count invariant failed")
                if previous is not None and state[key][team] < previous[key][team]:
                    raise ValueError("Monotonic-count invariant failed")
        previous = state
    return {"status": "passed", "logical_seconds_checked": end - start + 1,
            "checks": ["possession_time_conservation", "completed_passes_within_passes",
                       "goals_within_shots", "monotonic_nonnegative_counts"]}


def build_analysis_report(directory=DEFAULT_DATA):
    directory = Path(directory)
    catalog = Catalog(directory)
    audit = audit_dataset(directory, catalog)
    if audit["status"] != "passed":
        raise ValueError("Dataset audit failed; no analysis exported")
    fixture = catalog.fixtures["MM-DEMO-01"]
    match = fixture.match
    final = state_at(fixture, match["clip_end_sec"])
    summary, evidence = {}, {}
    for team in ("HOME", "AWAY"):
        rows = [e for e in fixture.events if e["team_id"] == team]
        evidence[team] = {
            "score": [e["event_id"] for e in rows if e["type"] == "goal"],
            "shots": [e["event_id"] for e in rows if e["type"] == "shot"],
            "passes": [e["event_id"] for e in rows if e["type"] == "pass"],
            "completed_passes": [e["event_id"] for e in rows if e["type"] == "pass" and e["outcome"] == "successful"],
        }
        for metric, ids in evidence[team].items():
            if len(ids) != final[metric][team]:
                raise ValueError("Metric contribution reconciliation failed")
        passes = final["passes"][team]
        summary[team] = {key: final[key][team] for key in evidence[team]}
        summary[team]["pass_accuracy_percent"] = round(100 * final["completed_passes"][team] / passes, 2) if passes else None
        summary[team]["synthetic_possession_seconds"] = final["possession_seconds"][team]
    primary = window_analysis(fixture, 1500, 1650, "HOME")
    negative = [window_analysis(fixture, 1500, 1559, "HOME"),
                window_analysis(fixture, 1500, 1650, "AWAY"),
                window_analysis(fixture, 1651, 1800, "HOME")]
    if not primary["heuristic_eligible"] or any(case["heuristic_eligible"] for case in negative):
        raise ValueError("Declared demo/control-window expectations failed")
    request = analysis_input(fixture, task_id="OFFLINE-B-1500-1650", replay_id="OFFLINE-B-DEMO", run_id=1)
    seconds = sorted({match["clip_start_sec"], match["clip_end_sec"], *[e["timestamp_sec"] for e in fixture.events]})
    return {"report_version": "b-analytics-1.0", "kind": "backend_data_audit", "status": "passed",
            "contract_version": "2.0.0", "synthetic": True, "model_calls": 0,
            "match": match, "event_count": len(fixture.events), "data_audit": audit,
            "input_sha256": {name: hashlib.sha256((directory / name).read_bytes()).hexdigest() for name in INPUT_FILES},
            "definitions": {"event_windows": "closed: start_sec <= timestamp_sec <= end_sec",
                            "possession_intervals": "half-open: [start_sec,end_sec)",
                            "clock_unit": "match logical seconds", "coordinates": "0..100, x right, y down",
                            "high_recovery_threshold_x": 66.67, "shot_link_max_delay_sec": 15,
                            "trigger": "at least 3 high recoveries, at least 2 linked recoveries",
                            "pass_accuracy": "successful pass events / all pass events; null if no passes",
                            "score": "goal events only; shot(outcome=goal) does not increment score"},
            "invariants": check_invariants(fixture), "team_summary": summary,
            "count_evidence_event_ids": evidence,
            "checkpoints": [state_at(fixture, sec) for sec in seconds],
            "primary_window": primary, "negative_controls": negative,
            "analysis_request_example": request,
            "example_identity_scope": "Offline reference IDs only; never publish against a runtime replay.",
            "limitations": list(LIMITATIONS)}


def markdown_report(report):
    lines = ["# MatchMind backend data analysis", "",
             "Deterministic engineering report. Synthetic data; no AI/model output.", "",
             f"Dataset: `{report['match']['generator_version']}`; contract: `{report['contract_version']}`; events: {report['event_count']}.",
             "Clip: first period, 25:00–30:00. Event windows are closed; possession intervals are half-open.", "",
             "## Clip totals", "", "| Team | Goals | Shots | Passes | Completed | Accuracy | Synthetic possession seconds |",
             "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for team, values in report["team_summary"].items():
        accuracy = "—" if values["pass_accuracy_percent"] is None else str(values["pass_accuracy_percent"]) + "%"
        lines.append(f"| {team} | {values['score']} | {values['shots']} | {values['passes']} | {values['completed_passes']} | {accuracy} | {values['synthetic_possession_seconds']} |")
    metrics = report["primary_window"]["metrics"]
    lines += ["", "## Fixed observed window: HOME, 1500–1650", "",
              f"{metrics['high_recoveries']} high recoveries; {metrics['linked_shots']} linked recoveries. The heuristic is eligible; tactical causality is not established.", "",
              "| Recovery | Attack-normalized x | Linked shot (delay seconds) |", "| --- | ---: | --- |"]
    for chain in report["primary_window"]["recovery_chains"]:
        shots = ", ".join(f"{shot['event_id']} ({shot['delay_sec']})" for shot in chain["linked_shots"]) or "None in the observed 15-second association window"
        lines.append(f"| {chain['recovery_event_id']} | {chain['attack_normalized_x']} | {shots} |")
    lines += ["", "## Negative controls", "", "| Team/window | High recoveries | Linked recoveries | Heuristic eligible |", "| --- | ---: | ---: | --- |"]
    for case in report["negative_controls"]:
        lines.append(f"| {case['team_id']} {case['window']['start_sec']}–{case['window']['end_sec']} | {case['metrics']['high_recoveries']} | {case['metrics']['linked_shots']} | {case['heuristic_eligible']} |")
    lines += ["", "## Verification and provenance", "",
              f"Data audit passed; conservation and count invariants checked at {report['invariants']['logical_seconds_checked']} logical seconds.",
              "The JSON report carries event contributions, possession intervals, event-time checkpoints and source hashes. analysis-request.json uses the frozen C interface with offline-only identities.", "",
              "| Input file | SHA-256 |", "| --- | --- |"]
    lines += [f"| {name} | `{digest}` |" for name, digest in report["input_sha256"].items()]
    lines += ["", "## Scope and limitations", "", *["- " + item for item in report["limitations"]], ""]
    return "\n".join(lines)


def output_directory(output):
    output = Path(output).resolve()
    allowed = [ROOT / ".artifacts", ROOT / "backend", ROOT / "deploy", ROOT / "data/extra"]
    repository = ROOT.parent if (ROOT.parent / ".git").exists() else ROOT
    if output.is_relative_to(repository.resolve()) and not any(output.is_relative_to(path.resolve()) for path in allowed):
        raise ValueError("Generated reports must not write to shared or other-role repository paths")
    return output


def export_analysis(report, output):
    output = output_directory(output)
    output.mkdir(parents=True, exist_ok=True)
    files = {"data-analysis.json": canonical(report), "data-analysis.md": markdown_report(report),
             "analysis-request.json": canonical(report["analysis_request_example"])}
    for name, value in files.items():
        (output / name).write_text(value, encoding="utf-8", newline="\n")
    return sorted(files)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--output-dir", type=Path, help="Explicit destination for three generated analysis files")
    args = parser.parse_args()
    try:
        report = build_analysis_report(args.data_dir)
        if args.output_dir:
            files = export_analysis(report, args.output_dir)
            print(canonical({"status": "passed", "files": files, "model_calls": 0}), end="")
        else:
            print(canonical(report), end="")
        return 0
    except (ValueError, KeyError, OSError):
        print(canonical({"status": "failed", "reason": "Data analysis validation failed; inspect offline preflight."}), end="")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
