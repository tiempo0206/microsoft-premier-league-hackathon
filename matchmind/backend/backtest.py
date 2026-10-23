"""Synthetic correctness regression for B; no training, tuning or model calls."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import tempfile

from data.generator.scenarios import SOURCE, VERSION, cases
from .data import Fixture
from .inputs import analysis_input
from .reporting import canonical, check_invariants, output_directory
from .stats import high_press_detected, state_at, window_metrics

COUNT_KEYS = ("score", "shots", "passes", "completed_passes", "possession_seconds")


def jsonline(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)+"\n").encode("utf-8")


def run_backtest(output=None, supplied_cases=None):
    dataset = list(cases()) if supplied_cases is None else list(supplied_cases)
    if not dataset or len({case["case_id"] for case in dataset}) != len(dataset):
        raise ValueError("Backtest cases must be nonempty with unique IDs")
    if output is not None:
        output = output_directory(output)
        output.mkdir(parents=True, exist_ok=True)
    normal_bytes = b"".join(jsonline(case) for case in dataset if case["kind"] == "normal")
    invalid_bytes = b"".join(jsonline(case) for case in dataset if case["kind"] == "invalid")
    encoded = normal_bytes + invalid_bytes
    source_license = json.loads((SOURCE.parent / "PROVENANCE.json").read_text(encoding="utf-8"))["license"]
    rows, orientations, teams = [], {}, {}
    snapshots = seconds = orientation_checks = team_checks = 0
    false_triggers = missed_triggers = suppressed = evaluated = 0
    expected_triggers = sum(case["kind"] == "normal" and case["expected"]["trigger"] for case in dataset)
    with tempfile.TemporaryDirectory(prefix="matchmind-backtest-", dir=output) as scratch:
        match_path = Path(scratch) / "case.match.json"
        event_path = Path(scratch) / "case.events.jsonl"
        for case in dataset:
            issues, loaded, actual_trigger = [], None, None
            match_path.write_text(canonical(case["match"]), encoding="utf-8", newline="\n")
            event_path.write_bytes(b"".join(jsonline(event) for event in case["events"]))
            try:
                loaded = Fixture.load(match_path)
            except ValueError:
                if case["kind"] != "invalid" or case["expected"]["mechanism"] != "loader_error":
                    issues.append("unexpected_loader_rejection")
            if case["kind"] == "invalid":
                if case["expected"]["mechanism"] == "loader_error" and loaded is not None:
                    issues.append("invalid_input_was_accepted")
                if case["expected"]["mechanism"] == "goal_relation_warning" and (loaded is None or not loaded.warnings):
                    issues.append("goal_relation_was_not_flagged")
            elif loaded is not None:
                if loaded.warnings:
                    issues.append("normal_goal_relation_failed")
                try:
                    actual_states = [state_at(loaded, expected["at_sec"]) for expected in case["expected"]["states"]]
                    snapshots += len(actual_states)
                    if actual_states != case["expected"]["states"]:
                        issues.append("snapshot_oracle_mismatch")
                    metrics = window_metrics(loaded, 1500, 1650, case["subject_team"])
                    if metrics != case["expected"]["metrics"]:
                        issues.append("metric_oracle_mismatch")
                    trigger, expected = high_press_detected(metrics), case["expected"]["trigger"]
                    actual_trigger = trigger
                    evaluated += 1
                    false_triggers += int(trigger and not expected)
                    missed_triggers += int(expected and not trigger)
                    suppressed += int(not trigger and not expected)
                    if trigger != expected:
                        issues.append("trigger_oracle_mismatch")
                    if trigger:
                        request = analysis_input(loaded, replay_id="OFFLINE-"+case["case_id"], run_id=1,
                                                 task_id="OFFLINE-TASK", team_id=case["subject_team"])
                        if request["metrics"] != case["expected"]["metrics"]:
                            issues.append("handoff_request_mismatch")
                    seconds += check_invariants(loaded)["logical_seconds_checked"]
                    key = case["split"], case["seed"], case["pattern"], case["subject_team"]
                    if key in orientations:
                        orientation_checks += 1
                        if orientations[key] != metrics:
                            issues.append("direction_mirror_mismatch")
                    else:
                        orientations[key] = metrics
                    key = case["split"], case["seed"], case["pattern"], case["direction"]
                    normalized = [{key: {"subject": state[key][case["subject_team"]],
                                         "opponent": state[key]["AWAY" if case["subject_team"] == "HOME" else "HOME"]}
                                   for key in COUNT_KEYS} for state in actual_states]
                    if key in teams:
                        team_checks += 1
                        if teams[key] != normalized:
                            issues.append("team_swap_mismatch")
                    else:
                        teams[key] = normalized
                except Exception as error:
                    issues.append("normal_case_exception:"+type(error).__name__)
            row = {"case_id": case["case_id"], "kind": case["kind"], "split": case["split"],
                   "passed": not issues, "issues": issues}
            if case["kind"] == "normal":
                row.update(expected_trigger=case["expected"]["trigger"], actual_trigger=actual_trigger)
            rows.append(row)
    by_split = {}
    for split in sorted({case["split"] for case in dataset}):
        selected = [row for row in rows if row["split"] == split]
        normal = [row for row in selected if row["kind"] == "normal"]
        by_split[split] = {"cases": len(selected), "failed": sum(not row["passed"] for row in selected),
                           "normal_cases": len(normal), "invalid_cases": len(selected)-len(normal),
                           "false_triggers": sum(row["actual_trigger"] is True and not row["expected_trigger"] for row in normal),
                           "missed_triggers": sum(row["actual_trigger"] is False and row["expected_trigger"] for row in normal),
                           "unevaluated_normal_windows": sum(row["actual_trigger"] is None for row in normal),
                           "seeds": sorted({case["seed"] for case in dataset if case["split"] == split})}
    report = {"status": "passed" if all(row["passed"] for row in rows) else "failed",
              "generator_version": VERSION, "purpose": "deterministic_backend_regression",
              "suite_scope": "full_fixed_suite" if supplied_cases is None else "supplied_subset",
              "training_performed": False, "parameters_tuned": False, "model_calls": 0,
              "dataset_sha256": hashlib.sha256(encoded).hexdigest(), "dataset_bytes": len(encoded),
              "dataset_hash_order": ["normal-scenarios.jsonl", "invalid-cases.jsonl"],
              "artifact_sha256": {"normal-scenarios.jsonl": hashlib.sha256(normal_bytes).hexdigest(),
                                  "invalid-cases.jsonl": hashlib.sha256(invalid_bytes).hexdigest()},
              "source_match_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
              "source_match_license": source_license,
              "normal_cases": sum(case["kind"] == "normal" for case in dataset),
              "invalid_cases": sum(case["kind"] == "invalid" for case in dataset),
              "cases_passed": sum(row["passed"] for row in rows), "cases_failed": sum(not row["passed"] for row in rows),
              "snapshot_comparisons": snapshots, "logical_seconds_checked": seconds,
              "direction_mirror_comparisons": orientation_checks, "team_swap_comparisons": team_checks,
              "expected_positive_windows": expected_triggers, "false_triggers": false_triggers,
              "evaluated_normal_windows": evaluated,
              "missed_triggers": missed_triggers, "correctly_suppressed_windows": suppressed,
              "normal_pattern_coverage": dict(sorted(Counter(case["pattern"] for case in dataset if case["kind"] == "normal").items())),
              "invalid_pattern_coverage": dict(sorted(Counter(case["fault"] for case in dataset if case["kind"] == "invalid").items())),
              "splits": by_split, "results": rows,
              "limitations": ["Finite sparse synthetic templates, not real league or complete-match simulation.",
                              "Seed holdout shares templates with development; no claim of real-world generalization.",
                              "Thresholds are frozen contract rules, not fitted from these cases.",
                              "Goal mismatch is flagged by the existing loader warning; strict runtime audit remains separate."]}
    if output is not None:
        (output / "normal-scenarios.jsonl").write_bytes(normal_bytes)
        (output / "invalid-cases.jsonl").write_bytes(invalid_bytes)
        (output / "backtest.json").write_text(canonical(report), encoding="utf-8", newline="\n")
        failed = {row["case_id"] for row in rows if not row["passed"]}
        (output / "failing-cases.jsonl").write_bytes(b"".join(jsonline(case) for case in dataset if case["case_id"] in failed))
        lines = ["# B synthetic regression", "", "No model training, parameter tuning or live API calls.", "",
                 f"Status: {report['status']}; normal: {report['normal_cases']}; invalid: {report['invalid_cases']}; failed: {report['cases_failed']}.",
                 f"Dataset SHA-256: `{report['dataset_sha256']}`.", "",
                 "| Split | Normal | Invalid | Failed | False/missed triggers | Seeds |", "| --- | ---: | ---: | ---: | --- | --- |"]
        lines += [f"| {split} | {value['normal_cases']} | {value['invalid_cases']} | {value['failed']} | {value['false_triggers']}/{value['missed_triggers']} | {value['seeds']} |" for split, value in by_split.items()]
        lines += ["", f"Snapshot comparisons: {snapshots}; logical seconds checked: {seconds}.",
                  f"Direction mirrors: {orientation_checks}; team swaps: {team_checks}.",
                  f"False triggers: {false_triggers}; missed triggers: {missed_triggers}.", "",
                  *["- "+item for item in report["limitations"]], ""]
        (output / "backtest.md").write_text("\n".join(lines), encoding="utf-8", newline="\n")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    report = run_backtest(args.output_dir)
    print(canonical({key: value for key, value in report.items() if key != "results"}), end="")
    return 0 if report["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
