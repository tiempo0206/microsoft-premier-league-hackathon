"""Export B-owned, zero-model-call inputs for A/C and the release integrator."""
import argparse
import copy
import hashlib
import json
from pathlib import Path

from .audit import ROOT, audit_dataset
from .data import Catalog
from .inputs import analysis_input
from .reporting import canonical, check_invariants, output_directory
from .stats import high_press_detected, recovery_chains, state_at, window_metrics
from contracts.validation import check_request
from data.generator.showcase import SCENARIOS, OUTPUT, VERSION, contents


def build_packet():
    requests, labels, reports = [], [], []
    for scenario in SCENARIOS:
        directory = OUTPUT / scenario
        if any(not (directory / name).is_file() or (directory / name).read_bytes() != value
               for name, value in contents(scenario).items()):
            raise ValueError("Showcase bytes differ from their generator")
        audit = audit_dataset(directory)
        if audit["status"] != "passed":
            raise ValueError("Showcase dataset audit failed")
        fixture = next(iter(Catalog(directory).fixtures.values()))
        windows = []
        for start, end in ((1500, 1650), (1651, 1800)):
            metrics = window_metrics(fixture, start, end)
            eligible = high_press_detected(metrics)
            windows.append({"window": {"start_sec": start, "end_sec": end},
                            "metrics": metrics, "heuristic_eligible": eligible,
                            "evidence_chains": recovery_chains(fixture, start, end)})
            for language in ("en", "zh"):
                task = f"OFFLINE-B-{scenario}-{start}-{end}-{language}"
                request = analysis_input(fixture, replay_id="OFFLINE-B-SHOWCASE", run_id=1,
                                         task_id=task, start_sec=start, end_sec=end, language=language)
                check_request(request)
                requests.append(request)
                labels.append({"task_id": task, "scenario": scenario, "language": language,
                               "heuristic_eligible": eligible,
                               "expected_handling": "analyze observed facts; never infer causation or future events"})
        reports.append({"scenario": scenario, "match": fixture.match,
                        "events": len(fixture.events), "dataset_audit": audit,
                        "invariants": check_invariants(fixture), "windows": windows,
                        "state_at_1650": state_at(fixture, 1650),
                        "final_state": state_at(fixture, 1800)})
    # Corruptions are evaluation inputs ONLY, never runtime fixtures. Two violate
    # the request contract; the count corruption needs C's arithmetic gate.
    tampered = []
    positive = requests[0]
    for name in ("contradictory_count", "wrong_match", "future_event"):
        request = copy.deepcopy(positive)
        request["task_id"] = "OFFLINE-B-TAMPER-" + name
        if name == "contradictory_count":
            request["metrics"]["high_recoveries"] = 99
        elif name == "wrong_match":
            request["events"][0]["match_id"] = "WRONG-MATCH"
        else:
            request["events"][0]["timestamp_sec"] = 1700
        tampered.append({"case_id": name, "expected": "reject before model call",
                         "request": request, "runtime_fixture": False})
    return {"packet_version": "b-handoff-1.0", "dataset_version": VERSION,
            "contract_version": "2.0.0", "model_calls": 0, "synthetic": True,
            "requests": requests, "labels": labels, "tampered": tampered, "reports": reports,
            "limitations": ["Three authored templates, not independent real-match samples.",
                            "Eligibility labels describe a fixed rule, not model accuracy or tactical causation.",
                            "Quiet/delayed requests help test C directly; runtime correctly does not schedule them.",
                            "Reports are deterministic B analyses, never AI insight cards."]}


def export_packet(output):
    # Reuse the B-owned output guard and never write into A/C/shared paths.
    output = output_directory(output)
    if output.is_relative_to(OUTPUT.resolve()):
        raise ValueError("Do not mix generated reports with audited runtime data")
    packet = build_packet()
    files = {"showcase-report.json": canonical({k: v for k, v in packet.items()
                                                if k not in ("requests", "tampered")}),
             "analysis-requests.jsonl": "".join(json.dumps(row, ensure_ascii=False, sort_keys=True)+"\n"
                                                for row in packet["requests"]),
             "tampered-requests.jsonl": "".join(json.dumps(row, ensure_ascii=False, sort_keys=True)+"\n"
                                                for row in packet["tampered"])}
    summary = ["# B showcase handoff", "", "Synthetic data; deterministic facts; model calls: 0.", "",
               "| Scenario | Events | High recoveries | Linked recoveries | HOME score at 1650 | Eligible |",
               "| --- | ---: | ---: | ---: | ---: | --- |"]
    for report in packet["reports"]:
        window = report["windows"][0]
        summary.append(f"| {report['scenario']} | {report['events']} | {window['metrics']['high_recoveries']} | "
                       f"{window['metrics']['linked_shots']} | {report['state_at_1650']['score']['HOME']} | "
                       f"{window['heuristic_eligible']} |")
    summary += ["", "12 valid AnalysisRequest rows: 3 scenarios × 2 observed windows × 2 languages.",
                "Three corruptions are in a separate file. They must never enter the runtime catalogue.",
                "The positive primary window contains its goal. The third recovery is NOT linked to a shot.",
                "Never claim that all three recoveries caused a shot or that this proves tactical causality.",
                "", *["- "+line for line in packet["limitations"]], ""]
    files["README.md"] = "\n".join(summary)
    files["manifest.json"] = canonical({"packet_version": packet["packet_version"], "model_calls": 0,
        "contract_version": "2.0.0", "valid_requests": 12, "tampered_requests": 3,
        "artifact_sha256": {name: hashlib.sha256(value.encode("utf-8")).hexdigest()
                            for name, value in files.items()}})
    output.mkdir(parents=True, exist_ok=True)
    for name, value in files.items():
        (output / name).write_text(value, encoding="utf-8", newline="\n")
    return {"status": "passed", "files": sorted(files), "valid_requests": 12,
            "tampered_requests": 3, "model_calls": 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT/".artifacts/backend-showcase")
    args = parser.parse_args()
    try:
        report = export_packet(args.output_dir)
    except (ValueError, KeyError, OSError):
        print(canonical({"status": "failed", "reason": "Showcase validation or output boundary failed"}), end="")
        return 2
    print(canonical(report), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
