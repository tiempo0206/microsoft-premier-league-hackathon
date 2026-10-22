"""Calibrate the semantic auditor: how often does it reject a card that is actually fine?

The code verifier's false-alarm rate is measured by `factcheck_bench` with zero cost. The auditor
is a model, so its false-alarm rate cannot be measured by a unit test — it needs real calls. That
gap matters: the auditor currently objects to almost every first draft, which costs one extra model
call per published card and, worse, makes the visible correction look staged rather than genuine.

This harness runs the auditor on claim sets that the code gate already accepted and that contain no
overreach, and reports its approval rate. A well-calibrated auditor approves nearly all of them.

    python -m evaluation.auditor_calibration            # 5 runs per case, billable
    python -m evaluation.auditor_calibration --runs 2
"""
import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai.config import from_env                       # noqa: E402
from ai.prompts import AUDITOR_SYSTEM, claims_block, facts_block   # noqa: E402
from ai.provider import ChatCompletionsProvider      # noqa: E402
from ai.service import _audit_approved               # noqa: E402
from ai.verify import allowed_numbers, check_claims, check_narratives   # noqa: E402
from backend.data import Catalog                     # noqa: E402
from backend.inputs import analysis_input            # noqa: E402

OUT = ROOT / ".artifacts" / "auditor"
DATA_DIR = ROOT / "data" / "extra" / "validated-demo"

# Every claim set here states exactly the supplied metric values and contains no causal claim, so
# the correct answer is "approved". Anything else is a false alarm.
GOOD_CASES = [
    {
        "label": "restates three metrics plainly",
        "claims": [
            {"claim_id": "C1", "kind": "metric",
             "text": "HOME made 3 high recoveries in this window.",
             "metric_key": "high_recoveries", "metric_value": 3,
             "evidence_event_ids": ["MM-DEMO-01-E007", "MM-DEMO-01-E013", "MM-DEMO-01-E019"]},
            {"claim_id": "C2", "kind": "metric",
             "text": "2 of those 3 recoveries were followed by a shot within 15 seconds.",
             "metric_key": "linked_shots", "metric_value": 2,
             "evidence_event_ids": ["MM-DEMO-01-E007", "MM-DEMO-01-E009",
                                    "MM-DEMO-01-E013", "MM-DEMO-01-E015"]},
            {"claim_id": "C3", "kind": "interpretation",
             "text": "The recoveries were concentrated in the attacking third.",
             "metric_key": None, "metric_value": None,
             "evidence_event_ids": ["MM-DEMO-01-E007", "MM-DEMO-01-E013"]},
        ],
        "narratives": {
            "casual": "The home side won the ball high up the pitch 3 times, and 2 of those turned into shots.",
            "analyst": ("HOME recorded 3 high recoveries and 2 linked shots in this window, with "
                        "possession running 35 seconds to AWAY's 115."),
        },
    },
    {
        "label": "states zero without a digit",
        "claims": [
            {"claim_id": "C1", "kind": "metric",
             "text": "AWAY took no shots in this window.",
             "metric_key": "away_shots", "metric_value": 0,
             "evidence_event_ids": ["MM-DEMO-01-E003"]},
            {"claim_id": "C2", "kind": "metric",
             "text": "HOME took 2 shots in this window.",
             "metric_key": "home_shots", "metric_value": 2,
             "evidence_event_ids": ["MM-DEMO-01-E009", "MM-DEMO-01-E015"]},
        ],
        "narratives": {
            "casual": "The home side had two shots and the visitors had none.",
            "analyst": "HOME recorded 2 shots to AWAY's 0 in this window.",
        },
    },
]


def build_request():
    fixture = Catalog(DATA_DIR).fixtures["MM-DEMO-01"]
    return analysis_input(fixture, replay_id="R-CAL", run_id=1, task_id="TASK-CAL",
                          start_sec=1500, end_sec=1650)


async def run_case(case, request, provider, runs):
    facts = facts_block(request, allowed_numbers=allowed_numbers(request))
    approved_claims, rejected, claim_issues = check_claims(case["claims"], request)
    narratives, narrative_issues = check_narratives(case["narratives"], request, approved_claims)
    entry = {"label": case["label"], "code_gate": {"approved": len(approved_claims),
                                                   "rejected": rejected,
                                                   "issues": claim_issues + narrative_issues},
             "runs": []}
    if not approved_claims or narratives is None:
        entry["skipped"] = "the code gate rejected this case, so it is not a false-alarm test"
        return entry
    for index in range(runs):
        started = time.monotonic()
        try:
            raw = await provider.complete_json(
                system=AUDITOR_SYSTEM,
                user=(facts + "\n\nCLAIMS:\n" + claims_block(approved_claims)
                      + "\n\nNARRATIVES:\n" + claims_block(narratives)),
                deadline=time.monotonic() + 30, max_tokens=500)
        except Exception as error:                   # noqa: BLE001 - a row, not a crash
            entry["runs"].append({"run": index, "error": type(error).__name__})
            continue
        approved, issues, _rejected = _audit_approved(raw)
        entry["runs"].append({"run": index, "approved": approved,
                              "issues": issues[:2],
                              "elapsed_ms": round((time.monotonic() - started) * 1000)})
    approved_runs = sum(1 for r in entry["runs"] if r.get("approved"))
    total = sum(1 for r in entry["runs"] if "approved" in r)
    entry["approval_rate"] = round(100.0 * approved_runs / total, 1) if total else None
    return entry


async def main_async(args):
    config = from_env()
    if not config.configured:
        print(json.dumps({"error": "no model configured"}, indent=2))
        return 1
    request = build_request()
    provider = ChatCompletionsProvider(config, use_cache=False)
    results = [await run_case(case, request, provider, args.runs) for case in GOOD_CASES]
    total_runs = sum(len([r for r in e["runs"] if "approved" in r]) for e in results)
    approved = sum(sum(1 for r in e["runs"] if r.get("approved")) for e in results)
    summary = {
        "config": config.public(),
        "cases": len(results),
        "runs": total_runs,
        "approved": approved,
        "false_alarm_rate": round(100.0 * (total_runs - approved) / total_runs, 1)
        if total_runs else None,
        "interpretation": ("A false alarm is the auditor rejecting a card the code gate accepted and "
                           "that states only supplied numbers. A high rate means the visible "
                           "correction is staged rather than genuine, and it costs an extra model "
                           "call per card."),
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "report.json").write_text(
        json.dumps({"summary": summary, "cases": results}, ensure_ascii=False, indent=2),
        encoding="utf-8")
    print(json.dumps({"summary": summary, "cases": results}, ensure_ascii=False, indent=2))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description="Auditor false-alarm calibration")
    parser.add_argument("--runs", type=int, default=5,
                        help="repetitions per case; the auditor is stochastic")
    return asyncio.run(main_async(parser.parse_args(argv)))


if __name__ == "__main__":
    raise SystemExit(main())
