"""How good is the verifier, actually?

Two numbers judges and reviewers will ask for, which a README claim cannot answer:

* **Catch rate** - of known-bad explanations, how many does the deterministic verifier
  reject? Measured per corruption category, because "98% caught" hides which 2% matters.
* **False-alarm rate** - of known-good explanations, how many does it wrongly reject?
  A verifier that blocks everything has a 100% catch rate and is worthless.

No model, no network, no cost: this exercises `ai/verify.py` directly. Run it any time.

    .\\.venv\\Scripts\\python.exe -m evaluation.factcheck_bench
"""
import copy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUEST = json.loads((ROOT / "contracts/examples/analysis_request.json").read_text(encoding="utf-8"))

from ai.verify import (check_claims, check_narratives,  # noqa: E402
                       consistency_issues, states_value, stray_numbers,
                       unsupported_phrases)

GOOD_CLAIMS = [
    {"claim_id": "C1", "kind": "metric",
     "text": "The home side made 3 high recoveries in this window.",
     "metric_key": "high_recoveries", "metric_value": 3,
     "evidence_event_ids": ["MM-DEMO-01-E007", "MM-DEMO-01-E013", "MM-DEMO-01-E019"]},
    {"claim_id": "C2", "kind": "metric",
     "text": "Two of those recoveries produced a shot within 15 seconds.",
     "metric_key": "linked_shots", "metric_value": 2,
     "evidence_event_ids": ["MM-DEMO-01-E007", "MM-DEMO-01-E009",
                            "MM-DEMO-01-E013", "MM-DEMO-01-E015"]},
    {"claim_id": "C3", "kind": "interpretation",
     "text": "The side kept recovering the ball high and shooting quickly inside this window.",
     "metric_key": None, "metric_value": None,
     "evidence_event_ids": ["MM-DEMO-01-E007", "MM-DEMO-01-E019"]},
]
GOOD_NARRATIVE = {
    "casual": "The home side won the ball back high up the pitch three times and two of those became shots.",
    "analyst": ("Across the 150-second window, HOME made 3 high recoveries and 2 linked shots, "
                "while AWAY held possession for 115 seconds and took 0 shots."),
}


def _claims(**overrides):
    claims = copy.deepcopy(GOOD_CLAIMS)
    claims[0].update(overrides)
    return claims


def corruptions():
    """(category, description, claims, narratives, must_be_caught)."""
    cases = []

    def add(category, note, claims=None, narratives=None, must=True, language="en"):
        cases.append({"category": category, "note": note,
                      "claims": claims if claims is not None else copy.deepcopy(GOOD_CLAIMS),
                      "narratives": narratives if narratives is not None else dict(GOOD_NARRATIVE),
                      "must_be_caught": must, "language": language})

    add("wrong_metric_value", "metric_value says 9, backend computed 3",
        claims=_claims(metric_value=9))
    add("metric_value_not_in_text", "claims 3 recoveries but never states the number",
        claims=_claims(text="The side pressed high repeatedly."))
    add("invented_event_id", "cites an event that does not exist",
        claims=_claims(evidence_event_ids=["MM-DEMO-01-E999"]))
    add("event_outside_window", "cites a real match event from outside this window",
        claims=_claims(evidence_event_ids=["MM-DEMO-01-E022"]))
    add("claim_without_evidence", "no evidence at all",
        claims=_claims(evidence_event_ids=[]))
    add("unknown_metric_key", "invents a metric name",
        claims=_claims(metric_key="press_intensity", metric_value=3))
    add("empty_text", "empty claim text", claims=_claims(text="   "))
    add("unknown_kind", "claim kind outside the enum", claims=_claims(kind="opinion"))

    interpretation_number = copy.deepcopy(GOOD_CLAIMS)
    interpretation_number[2].update(text="Momentum shifted after 47 seconds.")
    add("stray_number_in_interpretation", "interpretation invents a number",
        claims=interpretation_number)
    fatigue = copy.deepcopy(GOOD_CLAIMS)
    fatigue[2].update(text="The opponent was clearly fatigued, so the press worked.")
    add("unsupported_causation", "attributes fatigue the window cannot show", claims=fatigue)
    quantifier = copy.deepcopy(GOOD_CLAIMS)
    quantifier[2].update(text="Each of the three recoveries produced a shot.")
    add("quantifier_overreach", "says all three when only two did", claims=quantifier,
        must=False)  # caught by the auditor agent, not by regex code
    numeric_interpretation = copy.deepcopy(GOOD_CLAIMS)
    numeric_interpretation[2].update(metric_key="high_recoveries", metric_value=3)
    add("interpretation_carrying_number", "interpretation supplies a metric fact",
        claims=numeric_interpretation)
    no_metric_claim = [copy.deepcopy(GOOD_CLAIMS[2])]
    add("no_metric_claim", "every claim is an interpretation", claims=no_metric_claim)

    add("narrative_stray_number", "narrative invents 12 shots",
        narratives={"casual": "They had 12 shots.", "analyst": GOOD_NARRATIVE["analyst"]})
    add("narrative_event_id_leak", "narrative shows a raw event id",
        narratives={"casual": "See MM-DEMO-01-E007.", "analyst": GOOD_NARRATIVE["analyst"]})
    add("narrative_fatigue", "narrative claims fatigue",
        narratives={"casual": GOOD_NARRATIVE["casual"],
                    "analyst": "HOME pressed harder because AWAY were exhausted."})
    add("narrative_missing_audience", "only one audience produced",
        narratives={"casual": GOOD_NARRATIVE["casual"]})
    add("narrative_empty", "empty prose",
        narratives={"casual": "", "analyst": GOOD_NARRATIVE["analyst"]})

    # Language and evidence-type coverage, added after a real regression: a Chinese request that
    # came back in English, and a recovery claim citing only a shot.
    add("wrong_language_english_for_chinese_request",
        "Chinese was requested, the prose is English",
        narratives={"casual": GOOD_NARRATIVE["casual"],
                    "analyst": GOOD_NARRATIVE["analyst"]}, language="zh")
    add("wrong_language_chinese_for_english_request",
        "English was requested, the prose is Chinese",
        narratives={"casual": "主队在前场抢回球权三次。",
                    "analyst": "本窗口记录到 3 次高位夺回。"}, language="en")
    recovery_backed_by_a_shot = copy.deepcopy(GOOD_CLAIMS)
    recovery_backed_by_a_shot[0]["evidence_event_ids"] = ["MM-DEMO-01-E009"]
    add("recovery_claim_citing_only_a_shot",
        "a high_recoveries claim cites a shot, which cannot demonstrate a recovery",
        claims=recovery_backed_by_a_shot)
    shots_backed_by_a_pass_only = copy.deepcopy(GOOD_CLAIMS)
    shots_backed_by_a_pass_only[1]["evidence_event_ids"] = ["MM-DEMO-01-E008"]
    add("shots_claim_citing_only_passes",
        "a linked_shots claim cites only passes",
        claims=shots_backed_by_a_pass_only)
    return cases


def clean_cases():
    """Explanations that are correct and must NOT be rejected."""
    cases = []
    cases.append({"category": "clean_example", "claims": copy.deepcopy(GOOD_CLAIMS),
                  "narratives": dict(GOOD_NARRATIVE)})

    zero = copy.deepcopy(GOOD_CLAIMS)
    zero[1] = {"claim_id": "C4", "kind": "metric",
               "text": "AWAY took no shots in this window.",
               "metric_key": "away_shots", "metric_value": 0,
               "evidence_event_ids": ["MM-DEMO-01-E003"]}
    cases.append({"category": "clean_zero_written_as_words", "claims": zero,
                  "narratives": dict(GOOD_NARRATIVE)})

    zh = copy.deepcopy(GOOD_CLAIMS)
    zh[0]["text"] = "主队在本窗口内完成3次高位抢回球权。"
    zh[1]["text"] = "其中两次在15秒内形成射门。"
    zh[2]["text"] = "主队持续在前场抢回球权并迅速完成射门。"
    zh[0]["evidence_event_ids"] = ["MM-DEMO-01-E007", "MM-DEMO-01-E013", "MM-DEMO-01-E019"]
    zh[1]["evidence_event_ids"] = ["MM-DEMO-01-E009", "MM-DEMO-01-E015"]
    cases.append({"category": "clean_chinese", "language": "zh", "claims": zh,
                  "narratives": {"casual": "这段时间主队抢回球权3次，还射了2次门；客队一次都没射门。",
                                 "analyst": "本窗口记录到 3 次高位夺回，其中 2 次在 15 秒内形成射门，"
                                            "持球时间为 35 秒对 115 秒。"}})
    narrative_says_no_shots = dict(GOOD_NARRATIVE)
    narrative_says_no_shots["casual"] = ("The home side won the ball back high up the pitch "
                                         "three times and two became shots.")
    cases.append({"category": "clean_narrative_rephrase", "claims": copy.deepcopy(GOOD_CLAIMS),
                  "narratives": narrative_says_no_shots})
    return cases


def evaluate():
    results = []
    for case in corruptions():
        request = copy.deepcopy(REQUEST)
        request["language"] = case.get("language", "en")
        approved, rejected, claim_issues = check_claims(case["claims"], request)
        narratives, narrative_issues = check_narratives(
            case["narratives"], request, approved if approved else [])
        caught = bool(rejected) or bool(claim_issues) or narratives is None
        # A corruption could also be visible only in the arithmetic gate.
        results.append({"kind": "corrupt", "category": case["category"],
                        "note": case["note"], "caught": caught,
                        "must_be_caught": case["must_be_caught"],
                        "rejected_claims": rejected,
                        "issues": (claim_issues + narrative_issues)[:3]})
    false_alarms = []
    for case in clean_cases():
        request = copy.deepcopy(REQUEST)
        request["language"] = case.get("language", "en")
        approved, rejected, claim_issues = check_claims(case["claims"], request)
        narratives, narrative_issues = check_narratives(case["narratives"], request, approved)
        ok = not rejected and not claim_issues and narratives is not None
        false_alarms.append({"kind": "clean", "category": case["category"], "ok": ok,
                             "rejected_claims": rejected,
                             "issues": (claim_issues + narrative_issues)[:3]})
    return results, false_alarms


def report(results, false_alarms):
    must = [r for r in results if r["must_be_caught"]]
    caught = [r for r in must if r["caught"]]
    summary = {
        "corruptions_total": len(results),
        "corruptions_required": len(must),
        "corruptions_caught": len(caught),
        "catch_rate": round(100.0 * len(caught) / len(must), 1) if must else None,
        "clean_total": len(false_alarms),
        "clean_passed": sum(1 for c in false_alarms if c["ok"]),
        "false_alarm_rate": round(
            100.0 * sum(1 for c in false_alarms if not c["ok"]) / len(false_alarms), 1)
        if false_alarms else None,
        "gaps": [{"category": r["category"], "note": r["note"]}
                 for r in results if r["must_be_caught"] and not r["caught"]],
        "false_alarms": [c for c in false_alarms if not c["ok"]],
    }
    return summary


def main():
    results, false_alarms = evaluate()
    summary = report(results, false_alarms)
    width = max(len(r["category"]) for r in results + [{"category": ""}]) + 2
    print("%-*s %-8s %s" % (width, "category", "caught", "note"))
    print("-" * 110)
    for row in results:
        if not row["must_be_caught"]:
            status = "auditor"
        else:
            status = "yes" if row["caught"] else "NOT CAUGHT"
        print("%-*s %-8s %s" % (width, row["category"], status, row["note"]))
    print()
    print("%-*s %-8s %s" % (width, "clean case", "ok", ""))
    print("-" * 110)
    for row in false_alarms:
        print("%-*s %-8s %s" % (width, row["category"], "yes" if row["ok"] else "FALSE ALARM",
                                "; ".join(row["issues"])[:70]))
    print()
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    out = ROOT / ".artifacts" / "factcheck"
    out.mkdir(parents=True, exist_ok=True)
    (out / "report.json").write_text(
        json.dumps({"summary": summary, "corruptions": results, "clean": false_alarms},
                   ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
