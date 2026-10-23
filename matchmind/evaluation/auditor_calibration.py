"""Calibrate the semantic auditor in both directions.

The code verifier is measured with zero cost by `factcheck_bench`. The auditor is a model, so its
behaviour cannot be measured by a unit test — it needs real calls. Two numbers matter, and a harness
that reports only one of them is easy to fool:

- **False-alarm rate.** The auditor rejects a card the code gate already accepted and that states
  only supplied numbers. A high rate means the visible correction is staged rather than genuine, and
  it costs an extra model call per card.
- **Miss rate.** The auditor approves a card that the code gate cannot fault but that is still
  overreach: a mechanism nobody measured, a player-level claim with no player data, a superlative
  that needs the whole match, or a correct number attached to the wrong team. This is the half that
  the product's whole claim rests on, because the code gate cannot see any of it.

A model that rejects everything scores 100% on the second and 0% on the first. Reporting both, on
the same run, is the only way the numbers mean anything. So each bad case also records whether the
rejection **named the planted claim** — catching a card by rejecting an honest claim in it is not a
catch, it is the false alarm wearing the miss's clothes.

    python -m evaluation.auditor_calibration                # 5 runs per case, billable
    python -m evaluation.auditor_calibration --runs 2
    python -m evaluation.auditor_calibration --only bad
    python -m evaluation.auditor_calibration --plan          # no calls, show the corpus and the gate
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
from ai.usage import describe as describe_usage      # noqa: E402
from ai.verify import (allowed_numbers, check_claims, check_narratives,   # noqa: E402
                       stray_numbers, unsupported_phrases)
from backend.data import Catalog                     # noqa: E402
from backend.inputs import analysis_input            # noqa: E402

OUT = ROOT / ".artifacts" / "auditor"
DATA_DIR = ROOT / "data" / "extra" / "validated-demo"
WINDOW = {"start_sec": 1500, "end_sec": 1650}

# --- honest cards: the correct answer is "approved" -------------------------------------------

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
    {
        "label": "hedged interpretation that stays inside the data",
        "claims": [
            {"claim_id": "C1", "kind": "metric",
             "text": "AWAY held the ball for 115 seconds of this window.",
             "metric_key": "away_possession_seconds", "metric_value": 115,
             "evidence_event_ids": ["MM-DEMO-01-E011", "MM-DEMO-01-E012"]},
            {"claim_id": "C2", "kind": "interpretation",
             "text": "AWAY circulated the ball in their own half without turning it into a shot.",
             "metric_key": None, "metric_value": None,
             "evidence_event_ids": ["MM-DEMO-01-E011", "MM-DEMO-01-E012", "MM-DEMO-01-E017"]},
        ],
        "narratives": {
            "casual": "The visitors kept the ball for most of this spell but never got a shot away.",
            "analyst": "AWAY held possession for 115 seconds against HOME's 35 and recorded no shots.",
        },
    },
]

# --- overreach the code gate cannot see: the correct answer is "rejected" ----------------------
#
# Every case below passes `check_claims` and `check_narratives` unchanged. That is the point: the
# arithmetic is right, the numbers are supplied, no forbidden phrase is used — and the card is still
# wrong. `target` is the claim id that a competent reviewer must name (or "narratives").
#
# `flaw` is the taxonomy, so the report can say which kind of overreach survives.

BAD_CASES = [
    {
        "label": "contradicts the possession split",
        "flaw": "contradicts_data",
        "target": "C2",
        "claims": [
            {"claim_id": "C1", "kind": "metric",
             "text": "HOME made 3 high recoveries in this window.",
             "metric_key": "high_recoveries", "metric_value": 3,
             "evidence_event_ids": ["MM-DEMO-01-E007", "MM-DEMO-01-E013", "MM-DEMO-01-E019"]},
            {"claim_id": "C2", "kind": "interpretation",
             "text": "HOME controlled the ball for most of the window.",
             "metric_key": None, "metric_value": None,
             "evidence_event_ids": ["MM-DEMO-01-E007", "MM-DEMO-01-E013"]},
        ],
        "narratives": {
            "casual": "HOME won the ball back high up the pitch three times.",
            "analyst": "HOME recorded 3 high recoveries in this window.",
        },
    },
    {
        "label": "correct value, wrong team",
        "flaw": "contradicts_data",
        "target": "C2",
        "claims": [
            {"claim_id": "C1", "kind": "metric",
             "text": "HOME had 3 high recoveries.",
             "metric_key": "high_recoveries", "metric_value": 3,
             "evidence_event_ids": ["MM-DEMO-01-E007", "MM-DEMO-01-E013", "MM-DEMO-01-E019"]},
            {"claim_id": "C2", "kind": "metric",
             "text": "AWAY took 2 shots in this window.",
             "metric_key": "home_shots", "metric_value": 2,
             "evidence_event_ids": ["MM-DEMO-01-E009", "MM-DEMO-01-E015"]},
        ],
        "narratives": {
            "casual": "The home side won the ball high up the pitch three times.",
            "analyst": "HOME recorded 3 high recoveries in this window.",
        },
    },
    {
        "label": "universal negative the window cannot support",
        "flaw": "contradicts_data",
        "target": "C2",
        "claims": [
            {"claim_id": "C1", "kind": "metric",
             "text": "HOME made 3 high recoveries in this window.",
             "metric_key": "high_recoveries", "metric_value": 3,
             "evidence_event_ids": ["MM-DEMO-01-E007", "MM-DEMO-01-E013", "MM-DEMO-01-E019"]},
            {"claim_id": "C2", "kind": "interpretation",
             "text": "AWAY never won the ball back in this spell.",
             "metric_key": None, "metric_value": None,
             "evidence_event_ids": ["MM-DEMO-01-E010", "MM-DEMO-01-E016"]},
        ],
        "narratives": {
            "casual": "HOME won the ball back three times in this spell.",
            "analyst": "HOME recorded 3 high recoveries in this window.",
        },
    },
    {
        "label": "quantifier overreach on the linked shots",
        "flaw": "contradicts_data",
        "target": "C2",
        "claims": [
            {"claim_id": "C1", "kind": "metric",
             "text": "2 recoveries were followed by a shot within 15 seconds.",
             "metric_key": "linked_shots", "metric_value": 2,
             "evidence_event_ids": ["MM-DEMO-01-E007", "MM-DEMO-01-E009",
                                    "MM-DEMO-01-E013", "MM-DEMO-01-E015"]},
            {"claim_id": "C2", "kind": "interpretation",
             "text": "Each of those recoveries turned into a shot.",
             "metric_key": None, "metric_value": None,
             "evidence_event_ids": ["MM-DEMO-01-E007", "MM-DEMO-01-E013"]},
        ],
        "narratives": {
            "casual": "Two recoveries became shots within 15 seconds.",
            "analyst": "HOME recorded 2 linked shots in this window.",
        },
    },
    {
        "label": "superlative that needs the whole match",
        "flaw": "unsupported_scope",
        "target": "C2",
        "claims": [
            {"claim_id": "C1", "kind": "metric",
             "text": "HOME made 3 high recoveries in this window.",
             "metric_key": "high_recoveries", "metric_value": 3,
             "evidence_event_ids": ["MM-DEMO-01-E007", "MM-DEMO-01-E013", "MM-DEMO-01-E019"]},
            {"claim_id": "C2", "kind": "interpretation",
             "text": "This was the most intense pressing spell of the match.",
             "metric_key": None, "metric_value": None,
             "evidence_event_ids": ["MM-DEMO-01-E007", "MM-DEMO-01-E013"]},
        ],
        "narratives": {
            "casual": "HOME won the ball back three times here.",
            "analyst": "HOME recorded 3 high recoveries in this window.",
        },
    },
    {
        "label": "player-level claim with no player data",
        "flaw": "unsupported_scope",
        "target": "C2",
        "claims": [
            {"claim_id": "C1", "kind": "metric",
             "text": "HOME made 3 high recoveries in this window.",
             "metric_key": "high_recoveries", "metric_value": 3,
             "evidence_event_ids": ["MM-DEMO-01-E007", "MM-DEMO-01-E013", "MM-DEMO-01-E019"]},
            {"claim_id": "C2", "kind": "interpretation",
             "text": "The AWAY right-back kept getting caught out of position.",
             "metric_key": None, "metric_value": None,
             "evidence_event_ids": ["MM-DEMO-01-E007", "MM-DEMO-01-E013"]},
        ],
        "narratives": {
            "casual": "HOME won the ball back three times here.",
            "analyst": "HOME recorded 3 high recoveries in this window.",
        },
    },
    {
        "label": "mechanism nobody measured",
        "flaw": "unsupported_mechanism",
        "target": "C2",
        "claims": [
            {"claim_id": "C1", "kind": "metric",
             "text": "2 recoveries were followed by a shot within 15 seconds.",
             "metric_key": "linked_shots", "metric_value": 2,
             "evidence_event_ids": ["MM-DEMO-01-E007", "MM-DEMO-01-E009",
                                    "MM-DEMO-01-E013", "MM-DEMO-01-E015"]},
            {"claim_id": "C2", "kind": "interpretation",
             "text": "The press worked because AWAY's midfield stopped tracking runners.",
             "metric_key": None, "metric_value": None,
             "evidence_event_ids": ["MM-DEMO-01-E007", "MM-DEMO-01-E013"]},
        ],
        "narratives": {
            "casual": "Two of the recoveries became shots.",
            "analyst": "HOME recorded 2 linked shots in this window.",
        },
    },
    {
        "label": "prediction dressed as analysis",
        "flaw": "unsupported_mechanism",
        "target": "C2",
        "claims": [
            {"claim_id": "C1", "kind": "metric",
             "text": "HOME made 3 high recoveries in this window.",
             "metric_key": "high_recoveries", "metric_value": 3,
             "evidence_event_ids": ["MM-DEMO-01-E007", "MM-DEMO-01-E013", "MM-DEMO-01-E019"]},
            {"claim_id": "C2", "kind": "interpretation",
             "text": "That pattern will decide the rest of the match.",
             "metric_key": None, "metric_value": None,
             "evidence_event_ids": ["MM-DEMO-01-E007", "MM-DEMO-01-E013"]},
        ],
        "narratives": {
            "casual": "HOME won the ball back three times here.",
            "analyst": "HOME recorded 3 high recoveries in this window.",
        },
    },
    {
        "label": "counterfactual with no basis",
        "flaw": "unsupported_mechanism",
        "target": "C2",
        "claims": [
            {"claim_id": "C1", "kind": "metric",
             "text": "AWAY took no shots in this window.",
             "metric_key": "away_shots", "metric_value": 0,
             "evidence_event_ids": ["MM-DEMO-01-E003"]},
            {"claim_id": "C2", "kind": "interpretation",
             "text": "Had AWAY turned that possession into a shot, the game would look different.",
             "metric_key": None, "metric_value": None,
             "evidence_event_ids": ["MM-DEMO-01-E011", "MM-DEMO-01-E012"]},
        ],
        "narratives": {
            "casual": "The visitors had the ball but no shots.",
            "analyst": "AWAY held possession for 115 seconds and recorded no shots.",
        },
    },
    {
        "label": "overreach in the prose, not the claims",
        "flaw": "narrative",
        "target": "narratives",
        "claims": [
            {"claim_id": "C1", "kind": "metric",
             "text": "HOME made 3 high recoveries in this window.",
             "metric_key": "high_recoveries", "metric_value": 3,
             "evidence_event_ids": ["MM-DEMO-01-E007", "MM-DEMO-01-E013", "MM-DEMO-01-E019"]},
        ],
        "narratives": {
            "casual": "Three times HOME won it back, and AWAY's shape collapsed once the press arrived.",
            "analyst": "HOME recorded 3 high recoveries in this window.",
        },
    },
]


def build_request(window=None):
    fixture = Catalog(DATA_DIR).fixtures["MM-DEMO-01"]
    window = window or WINDOW
    return analysis_input(fixture, replay_id="R-CAL", run_id=1, task_id="TASK-CAL",
                          start_sec=window["start_sec"], end_sec=window["end_sec"])


def gate(case, request):
    """Run the deterministic gate on a case and describe what it did.

    For a bad case, `code_gate_caught` must be False — otherwise the case is testing the code gate
    again and tells us nothing about the auditor.
    """
    approved_claims, rejected, claim_issues = check_claims(case["claims"], request)
    narratives, narrative_issues = check_narratives(case["narratives"], request, approved_claims)
    return {
        "approved_claims": approved_claims,
        "rejected": rejected,
        "issues": claim_issues + narrative_issues,
        "narratives": narratives,
    }


def code_gate_caught(case, gated):
    """True when the deterministic gate already blocks this case, in any of three ways."""
    if gated["rejected"]:
        return True
    if gated["narratives"] is None:
        return True
    target = case.get("target")
    if target and target != "narratives" and target in gated["rejected"]:
        return True
    return False


async def run_case(case, request, provider, runs, expect):
    gated = gate(case, request)
    entry = {"label": case["label"], "expect": expect,
             "flaw": case.get("flaw"), "target": case.get("target"),
             "code_gate": {"approved": len(gated["approved_claims"]),
                           "rejected": gated["rejected"],
                           "issues": gated["issues"]},
             "runs": []}
    if not gated["approved_claims"] or gated["narratives"] is None:
        entry["skipped"] = "the code gate rejected this case, so it is not an auditor test"
        return entry
    if len(gated["approved_claims"]) != len(case["claims"]):
        entry["skipped"] = "the code gate dropped a claim, so the case is no longer what it says"
        return entry
    facts = facts_block(request, allowed_numbers=allowed_numbers(request))
    for index in range(runs):
        started = time.monotonic()
        try:
            raw = await provider.complete_json(
                system=AUDITOR_SYSTEM,
                user=(facts + "\n\nCLAIMS:\n" + claims_block(gated["approved_claims"])
                      + "\n\nNARRATIVES:\n" + claims_block(gated["narratives"])),
                deadline=time.monotonic() + 30, max_tokens=500)
        except Exception as error:                   # noqa: BLE001 - a row, not a crash
            entry["runs"].append({"run": index, "error": type(error).__name__})
            continue
        approved, issues, rejected_claims = _audit_approved(raw)
        target = case.get("target")
        if expect == "rejected":
            named_target = (bool(raw.get("narrative_problems"))
                            if target == "narratives" else target in rejected_claims)
        else:
            named_target = None
        entry["runs"].append({"run": index, "approved": approved,
                              "caught": (not approved) if expect == "rejected" else None,
                              "named_target": named_target,
                              "rejected_claims": rejected_claims,
                              "issues": issues[:3],
                              "elapsed_ms": round((time.monotonic() - started) * 1000)})
    scored = [r for r in entry["runs"] if "approved" in r]
    if scored:
        approved_runs = sum(1 for r in scored if r["approved"])
        entry["approval_rate"] = round(100.0 * approved_runs / len(scored), 1)
        if expect == "rejected":
            entry["detection_rate"] = round(100.0 * (len(scored) - approved_runs) / len(scored), 1)
            named = sum(1 for r in scored if r.get("named_target"))
            entry["targeted_rate"] = round(100.0 * named / len(scored), 1)
    return entry


def _pct(numerator, denominator):
    return round(100.0 * numerator / denominator, 1) if denominator else None


def _scored(entry):
    return [run for run in entry.get("runs") or [] if "approved" in run]


def summarise(results):
    """Both halves, plus the number that makes them readable together.

    Counted straight from the runs rather than from the per-case rates, so the same code path
    scores a real report and a unit-test fixture.
    """
    good = [e for e in results if e["expect"] == "accepted" and _scored(e)]
    bad = [e for e in results if e["expect"] == "rejected"]
    bad_scored = [e for e in bad if _scored(e)]

    good_runs = sum(len(_scored(e)) for e in good)
    approved_runs = sum(sum(1 for r in _scored(e) if r.get("approved")) for e in good)
    bad_runs = sum(len(_scored(e)) for e in bad_scored)
    caught_runs = sum(sum(1 for r in _scored(e) if r.get("caught")) for e in bad_scored)
    named_runs = sum(sum(1 for r in _scored(e) if r.get("named_target")) for e in bad_scored)

    by_flaw = {}
    for entry in bad_scored:
        bucket = by_flaw.setdefault(entry["flaw"], {"cases": 0, "runs": 0, "caught": 0,
                                                    "named": 0})
        bucket["cases"] += 1
        for run in _scored(entry):
            bucket["runs"] += 1
            bucket["caught"] += 1 if run.get("caught") else 0
            bucket["named"] += 1 if run.get("named_target") else 0
    # A model that rejects everything looks perfect on the miss side. The honest headline is the
    # one that counts both: it only discriminates if it approves the good cards AND catches the bad.
    discrimination = None
    if good_runs and bad_runs:
        discrimination = round(_pct(approved_runs + caught_runs, good_runs + bad_runs), 1)

    return {
        "cases": len(results),
        "skipped": [e["label"] for e in results if "skipped" in e],
        "honest_cards": {
            "cases": len(good),
            "runs": good_runs,
            "approved": approved_runs,
            "false_alarm_rate": _pct(good_runs - approved_runs, good_runs),
        },
        "overreach_cards": {
            "cases": len(bad_scored),
            "runs": bad_runs,
            "caught": caught_runs,
            "named_the_planted_claim": named_runs,
            "miss_rate": _pct(bad_runs - caught_runs, bad_runs),
            "miss_rate_naming_the_planted_claim": _pct(bad_runs - named_runs, bad_runs),
            "by_flaw": {k: {"cases": v["cases"], "runs": v["runs"],
                            "caught_rate": _pct(v["caught"], v["runs"]),
                            "named_rate": _pct(v["named"], v["runs"])}
                        for k, v in sorted(by_flaw.items())},
        },
        "discrimination": {
            "correct_decisions": discrimination,
            "why_two_numbers": ("A model that rejects everything scores 100% on overreach and 0% on "
                                "honest cards. Only both halves, on the same run, say whether it "
                                "is reviewing or just suspicious."),
        },
        "interpretation": {
            "false_alarm": ("The auditor rejected a card the code gate accepted and that states only "
                            "supplied numbers. It costs an extra model call per card and makes the "
                            "visible correction look staged."),
            "overreach": ("The auditor approved a card whose arithmetic is right but whose claim is "
                          "not in the data. The code gate cannot see this class at all, so a miss "
                          "here reaches the viewer."),
            "named_the_planted_claim": ("The rejection named the claim that was actually rigged. "
                                        "A card can be blocked for the wrong reason, which is a "
                                        "false alarm inside a catch."),
        },
    }


def plan(request):
    """Show the corpus and what the deterministic gate does to it. No model calls."""
    rows = []
    for expect, corpus in (("accepted", GOOD_CASES), ("rejected", BAD_CASES)):
        for case in corpus:
            gated = gate(case, request)
            rows.append({
                "label": case["label"],
                "expect": expect,
                "flaw": case.get("flaw"),
                "target": case.get("target"),
                "code_gate_rejected_claims": gated["rejected"],
                "code_gate_issues": gated["issues"],
                "code_gate_blocked_whole_card": code_gate_caught(case, gated),
                "is_an_auditor_test": (not code_gate_caught(case, gated)
                                       and len(gated["approved_claims"]) == len(case["claims"])
                                       and gated["narratives"] is not None
                                       if expect == "rejected" else
                                       len(gated["approved_claims"]) == len(case["claims"])
                                       and gated["narratives"] is not None),
            })
    usable = [r for r in rows if r["is_an_auditor_test"]]
    return {
        "window": WINDOW,
        "cases": len(rows),
        "usable_as_auditor_tests": len(usable),
        "by_kind": {kind: sum(1 for r in rows if r["expect"] == kind)
                    for kind in ("accepted", "rejected")},
        "rows": rows,
    }


async def main_async(args):
    request = build_request()
    if args.plan:
        print(json.dumps(plan(request), ensure_ascii=False, indent=2))
        return 0
    config = from_env()
    if not config.configured:
        print(json.dumps({"error": "no model configured"}, indent=2))
        return 1
    provider = ChatCompletionsProvider(config, use_cache=False)
    selected = []
    if args.only in ("all", "good"):
        selected.extend((case, "accepted") for case in GOOD_CASES)
    if args.only in ("all", "bad"):
        selected.extend((case, "rejected") for case in BAD_CASES)
    results = [await run_case(case, request, provider, args.runs, expect)
               for case, expect in selected]
    report = {
        "config": config.public(),
        "window": WINDOW,
        "runs_per_case": args.runs,
        "usage": describe_usage(provider.usage),
        "summary": summarise(results),
        "cases": results,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2),
                                     encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Auditor calibration: false alarms on honest cards, misses on overreach")
    parser.add_argument("--runs", type=int, default=5,
                        help="repetitions per case; the auditor is stochastic")
    parser.add_argument("--only", choices=("all", "good", "bad"), default="all",
                        help="restrict to one half of the corpus")
    parser.add_argument("--plan", action="store_true",
                        help="print the corpus and what the code gate does to it; no model calls")
    return asyncio.run(main_async(parser.parse_args(argv)))


if __name__ == "__main__":
    raise SystemExit(main())
